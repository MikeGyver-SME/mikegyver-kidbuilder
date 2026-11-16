import Foundation
import SwiftUI
import UIKit

/// Owns the kid projects, the settings, the build log, and the code
/// fetched from the builder server.
///
/// Projects persist as one JSON file in Documents/KidBuilder/
/// projects.json, so they survive app restarts and can be inspected in
/// the Files app. Settings live in UserDefaults under the
/// "kidbuilder." prefix. The FTP password is NOT here - see
/// KeychainService. Build progress is owned by the store (a class) so
/// a background FTP progress callback can update it - a SwiftUI View
/// struct copy cannot.
///
/// There is deliberately no block-to-Rust generator in this app. The
/// Code tab asks the builder server (POST /generate-blocks) for the
/// real generated files, and shows them. If the server cannot be
/// reached, the tab says so - it never invents code.
enum BuildPhase: Equatable {
    case idle, building, uploading, done, failed
}

@MainActor
final class KidStore: ObservableObject {
    @Published var projects: [KidProject] = []
    @Published var selectedProjectID: UUID?
    @Published var logLines: [String] = []
    @Published var buildPhase: BuildPhase = .idle
    @Published var buildStatus = "Ready."
    @Published var generatedFiles: [BuilderService.SourceFile] = []
    @Published var codeStatus = "Tap \"Get my code\" to see the real Rust for this project."
    @Published var codeLoading = false

    // MARK: - Settings (UserDefaults; no secrets here)

    @AppStorage("kidbuilder.builderURL") var builderURL = ""
    @AppStorage("kidbuilder.ftpHost") var ftpHost = "ftp.mikegyver-studio.si"
    @AppStorage("kidbuilder.ftpUsername") var ftpUsername = "itsmikeg@mikegyver-studio.si"
    @AppStorage("kidbuilder.ftpPort") var ftpPort = 21
    @AppStorage("kidbuilder.rememberPassword") var rememberPassword = true
    @AppStorage("kidbuilder.lastDeployURL") var lastDeployURL = ""

    var hasSavedPassword: Bool {
        KeychainService.hasPassword(account: ftpUsername)
    }

    var selectedProject: KidProject? {
        get {
            guard let id = selectedProjectID else { return nil }
            return projects.first { $0.id == id }
        }
        set {
            guard let project = newValue,
                  let index = projects.firstIndex(where: { $0.id == project.id }) else { return }
            projects[index] = project
            saveProjects()
        }
    }

    var selectedSiteURL: String {
        selectedProject?.siteURL ?? "https://mikegyver-studio.si/kids/"
    }

    /// The generated src/main.rs for the selected project, if the Code
    /// tab has fetched it. Nil until fetched - never invented.
    var generatedMainRs: String? {
        generatedFiles.first { $0.path == "src/main.rs" }?.content
    }

    private var projectsFile: URL {
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return docs.appendingPathComponent("KidBuilder/projects.json")
    }

    init() {
        loadProjects()
        if selectedProjectID == nil {
            selectedProjectID = projects.first?.id
        }
    }

    // MARK: - Projects

    func loadProjects() {
        if let data = try? Data(contentsOf: projectsFile),
           let decoded = try? JSONDecoder().decode([KidProject].self, from: data),
           !decoded.isEmpty {
            projects = decoded
        } else {
            projects = KidProjects.starters()
            saveProjects()
        }
    }

    func saveProjects() {
        do {
            try FileManager.default.createDirectory(
                at: projectsFile.deletingLastPathComponent(),
                withIntermediateDirectories: true)
            let data = try JSONEncoder().encode(projects)
            try data.write(to: projectsFile, options: .atomic)
        } catch {
            log("Could not save projects: \(error.localizedDescription)")
        }
    }

    func addProject() {
        let count = projects.count + 1
        let slug = "my-app-\(count)"
        let project = KidProject(
            name: "My App \(count)",
            slug: slug,
            description: "A brand new app. Add some blocks!",
            deployPath: "/public_html/kids/\(slug)",
            blocks: [.title(text: "My App"), .words(text: "Hello, world!")])
        projects.append(project)
        selectedProjectID = project.id
        saveProjects()
    }

    func deleteProject(_ project: KidProject) {
        projects.removeAll { $0.id == project.id }
        if selectedProjectID == project.id {
            selectedProjectID = projects.first?.id
        }
        saveProjects()
    }

    func resetStarters() {
        projects = KidProjects.starters()
        selectedProjectID = projects.first?.id
        saveProjects()
        log("Starter projects restored.")
    }

    // MARK: - Blocks (edits to the selected project)

    func updateBlock(at index: Int, to block: KidBlock) {
        guard var project = selectedProject,
              project.blocks.indices.contains(index) else { return }
        project.blocks[index] = block
        selectedProject = project
        generatedFiles = []
        codeStatus = "You changed a block. Tap \"Get my code\" to see the new Rust."
    }

    func addBlock(kind: String) {
        guard var project = selectedProject else { return }
        project.blocks.append(KidBlock.blank(kind: kind))
        selectedProject = project
        generatedFiles = []
    }

    func deleteBlock(at offsets: IndexSet) {
        guard var project = selectedProject else { return }
        project.blocks.remove(atOffsets: offsets)
        selectedProject = project
        generatedFiles = []
    }

    func moveBlock(from source: IndexSet, to destination: Int) {
        guard var project = selectedProject else { return }
        project.blocks.move(fromOffsets: source, toOffset: destination)
        selectedProject = project
        generatedFiles = []
    }

    func updateDeployPath(_ path: String) {
        guard var project = selectedProject else { return }
        project.deployPath = path
        selectedProject = project
    }

    // MARK: - Code (from the builder server, never invented)

    func fetchCode() async {
        guard let project = selectedProject else {
            codeStatus = "Pick a project first."
            return
        }
        guard let baseURL = BuilderService.normalisedURL(builderURL) else {
            codeStatus = "Your code comes from the builder server. Set the builder address in Settings first, then tap \"Get my code\" again."
            return
        }
        codeLoading = true
        codeStatus = "Asking the builder for your code..."
        do {
            let response = try await BuilderService.generateBlocks(
                baseURL: baseURL, projectName: project.name, blocks: project.blocks)
            generatedFiles = response.files
            if response.mainRs != nil {
                codeStatus = "This is the real Rust the builder made from your blocks. Change a block and fetch it again to see it change."
            } else {
                codeStatus = "The builder answered but did not send a main.rs file. Its log says: \(response.log)"
            }
            log("Code fetched for \(project.name) (\(response.files.count) files).")
        } catch {
            generatedFiles = []
            codeStatus = "Could not reach the builder server to get your code. Check the builder address in Settings and that your PC is on, then try again. (\(error.localizedDescription))"
            log("Code fetch failed: \(error.localizedDescription)")
        }
        codeLoading = false
    }

    // MARK: - Log

    func log(_ line: String) {
        let stamp = DateFormatter.logTime.string(from: Date())
        logLines.append("[\(stamp)] \(line)")
    }

    func clearLog() { logLines.removeAll() }
}

private extension DateFormatter {
    static let logTime: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f
    }()
}

/// Photo helper: a photo block never stores a full-size photo.
///
/// Whatever the camera or the photo library hands back is shrunk to
/// fit inside 320x240 and saved as JPEG at quality 0.7, then stored
/// as base64 in the picture block. A 320x240 JPEG is a few tens of
/// kilobytes; a full iPhone photo is megabytes and would make every
/// project file and every build slow.
enum PhotoHelper {
    static func downscaledJPEGBase64(from image: UIImage) -> String? {
        let maxSize = CGSize(width: 320, height: 240)
        let scale = min(maxSize.width / image.size.width,
                        maxSize.height / image.size.height, 1.0)
        let newSize = CGSize(width: image.size.width * scale,
                             height: image.size.height * scale)
        let renderer = UIGraphicsImageRenderer(size: newSize)
        let small = renderer.image { _ in
            image.draw(in: CGRect(origin: .zero, size: newSize))
        }
        guard let data = small.jpegData(compressionQuality: 0.7) else { return nil }
        return data.base64EncodedString()
    }

    static func image(fromBase64 base64: String) -> UIImage? {
        guard !base64.isEmpty,
              let data = Data(base64Encoded: base64) else { return nil }
        return UIImage(data: data)
    }
}
