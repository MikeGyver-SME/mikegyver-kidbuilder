import SwiftUI
import PhotosUI
import UIKit

/// Kid Builder - stack blocks, tap Build, ship a real Yew/WASM site.
///
/// Tabs:
///   Projects - the five starters plus New project.
///   Blocks   - the block editor for the selected project.
///   Code     - "See my code": the real generated main.rs, fetched
///              from the builder server. Never invented on the phone.
///   Build    - Build & Deploy to FTP, build log, Open live site.
///   Settings - builder URL, FTP, password, connection tests.
///
/// Flow (see README.md for the why):
///   1. Blocks go to your builder server, which turns them into the
///      five Yew files, runs `trunk build --release`, and sends the
///      finished dist/ files back. An iPhone cannot run cargo/trunk.
///   2. This phone uploads dist/ to ftp.mikegyver-studio.si over FTP.
///      The password comes from the Keychain and never leaves the phone.
struct ContentView: View {
    @EnvironmentObject private var store: KidStore

    @State private var selectedTab = 0
    @State private var showPasswordSheet = false
    @State private var sheetPassword = ""
    @State private var sheetRemember = true
    @State private var showResetConfirm = false

    var body: some View {
        TabView(selection: $selectedTab) {
            projectsTab
                .tabItem { Label("Projects", systemImage: "folder") }
                .tag(0)
            blocksTab
                .tabItem { Label("Blocks", systemImage: "square.stack.3d.up") }
                .tag(1)
            codeTab
                .tabItem { Label("Code", systemImage: "curlybraces") }
                .tag(2)
            buildTab
                .tabItem { Label("Build", systemImage: "hammer") }
                .tag(3)
            settingsTab
                .tabItem { Label("Settings", systemImage: "gear") }
                .tag(4)
        }
        .sheet(isPresented: $showPasswordSheet) {
            passwordSheet
        }
        .alert("Bring back the five starter projects?", isPresented: $showResetConfirm) {
            Button("Bring them back", role: .destructive) { store.resetStarters() }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This replaces your project list with the five starters. Projects you made yourself will be gone.")
        }
    }

    // MARK: - Projects tab

    private var projectsTab: some View {
        NavigationStack {
            List {
                Section {
                    ForEach(store.projects) { project in
                        Button {
                            store.selectedProjectID = project.id
                            selectedTab = 1
                        } label: {
                            VStack(alignment: .leading, spacing: 2) {
                                HStack {
                                    Text(project.name).font(.headline)
                                    if project.id == store.selectedProjectID {
                                        Image(systemName: "checkmark.circle.fill")
                                            .foregroundStyle(.green)
                                    }
                                }
                                Text(project.description)
                                    .font(.subheadline).foregroundStyle(.secondary)
                                Text("\(project.blocks.count) blocks - \(project.siteURL)")
                                    .font(.caption).foregroundStyle(.secondary)
                            }
                        }
                    }
                    .onDelete { offsets in
                        for index in offsets { store.deleteProject(store.projects[index]) }
                    }
                } header: {
                    Text("Tap a project to build with it")
                } footer: {
                    Text("Colin and Luan each pick a project. The check mark shows which one the Blocks, Code and Build tabs are working on.")
                }
                Section {
                    Button("New project") { store.addProject(); selectedTab = 1 }
                    Button("Bring back the five starters", role: .destructive) {
                        showResetConfirm = true
                    }
                }
            }
            .navigationTitle("Kid Builder")
        }
    }

    // MARK: - Blocks tab

    private var blocksTab: some View {
        NavigationStack {
            if let project = store.selectedProject {
                List {
                    Section {
                        Text(project.description)
                            .font(.subheadline).foregroundStyle(.secondary)
                        ForEach(project.blocks.indices, id: \.self) { index in
                            NavigationLink(destination: BlockEditorView(blockIndex: index)) {
                                Label {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(project.blocks[index].displayName).font(.headline)
                                        Text(project.blocks[index].summary)
                                            .font(.subheadline).foregroundStyle(.secondary)
                                            .lineLimit(2)
                                    }
                                } icon: {
                                    Image(systemName: project.blocks[index].systemImage)
                                }
                            }
                        }
                        .onDelete { store.deleteBlock(at: $0) }
                        .onMove { store.moveBlock(from: $0, to: $1) }
                    } header: {
                        Text("\(project.name) - tap a block to change it, drag to reorder")
                    } footer: {
                        Text("Blocks run top to bottom on your web page. Swipe left to delete a block.")
                    }
                    Section {
                        Menu("Add a block") {
                            ForEach(KidBlock.allKinds, id: \.self) { kind in
                                Button(KidBlock.blank(kind: kind).displayName) {
                                    store.addBlock(kind: kind)
                                }
                            }
                        }
                    }
                }
                .navigationTitle(project.name)
                .toolbar { EditButton() }
            } else {
                VStack(spacing: 12) {
                    Text("Pick a project first.")
                        .font(.headline)
                    Text("Go to the Projects tab and tap one of the five starters, or make a new project.")
                        .font(.subheadline).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    Button("Go to Projects") { selectedTab = 0 }
                        .buttonStyle(.borderedProminent)
                }
                .padding()
                .navigationTitle("Blocks")
            }
        }
    }

    // MARK: - Code tab

    private var codeTab: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("See my code")
                            .font(.title2).bold()
                        Text("This is the real Rust your blocks turn into. The builder server writes it - this phone never makes it up.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }

                    Button(action: { Task { await store.fetchCode() } }) {
                        HStack {
                            Image(systemName: "curlybraces")
                            Text(store.codeLoading ? "Getting your code..." : "Get my code")
                                .bold()
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(store.codeLoading ? Color.gray : Color.accentColor)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(store.codeLoading || store.selectedProject == nil)

                    Text(store.codeStatus)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    if !store.generatedFiles.isEmpty {
                        GroupBox("Files the builder made") {
                            VStack(alignment: .leading, spacing: 4) {
                                ForEach(store.generatedFiles, id: \.path) { file in
                                    Text(file.path).font(.system(size: 13, design: .monospaced))
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                    }

                    if let mainRs = store.generatedMainRs {
                        GroupBox("src/main.rs") {
                            Text(mainRs)
                                .font(.system(size: 12, design: .monospaced))
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .textSelection(.enabled)
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Code")
        }
    }

    // MARK: - Build tab

    private var buildTab: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("Build & deploy")
                            .font(.title2).bold()
                        Text("Builds your blocks with Trunk, then uploads the finished site to FTP.")
                            .font(.subheadline).foregroundStyle(.secondary)
                    }

                    GroupBox {
                        VStack(alignment: .leading, spacing: 4) {
                            row("Project", store.selectedProject?.name ?? "None picked")
                            row("Builder", store.builderURL.isEmpty ? "Not set - see Settings" : store.builderURL)
                            row("FTP", "\(store.ftpUsername) @ \(store.ftpHost):\(store.ftpPort)")
                            row("Password", store.hasSavedPassword ? "Saved on this phone" : "Not saved yet")
                            row("Live site", store.selectedSiteURL)
                        }
                        .font(.subheadline)
                    }

                    if store.selectedProject != nil {
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Deploy folder (FTP)")
                                .font(.subheadline).bold()
                            TextField("/public_html/kids/my-app", text: Binding(
                                get: { store.selectedProject?.deployPath ?? "" },
                                set: { store.updateDeployPath($0) }))
                                .autocapitalization(.none)
                                .disableAutocorrection(true)
                                .textFieldStyle(.roundedBorder)
                                .font(.system(size: 15, design: .monospaced))
                            Text("Each build uses whatever is entered here. Folders that do not exist yet are created for you.")
                                .font(.caption).foregroundStyle(.secondary)
                        }
                    }

                    Button(action: startBuild) {
                        HStack {
                            Image(systemName: "hammer.fill")
                            Text(store.buildPhase == .building ? "Building..." : store.buildPhase == .uploading ? "Uploading..." : "Build & Deploy")
                                .bold()
                        }
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(store.buildPhase == .building || store.buildPhase == .uploading ? Color.gray : Color.accentColor)
                        .foregroundStyle(.white)
                        .clipShape(RoundedRectangle(cornerRadius: 12))
                    }
                    .disabled(store.buildPhase == .building || store.buildPhase == .uploading || store.selectedProject == nil)

                    Text(store.buildStatus)
                        .font(.subheadline)
                        .foregroundStyle(store.buildPhase == .failed ? .red : .secondary)

                    if store.buildPhase == .done {
                        Button("Open live site") {
                            if let url = URL(string: store.selectedSiteURL) {
                                UIApplication.shared.open(url)
                            }
                        }
                        .buttonStyle(.borderedProminent)
                    }

                    GroupBox("Build log") {
                        ScrollView {
                            VStack(alignment: .leading, spacing: 4) {
                                if store.logLines.isEmpty {
                                    Text("No builds yet. The log shows each step here.")
                                        .font(.caption).foregroundStyle(.secondary)
                                } else {
                                    ForEach(store.logLines.indices, id: \.self) { i in
                                        Text(store.logLines[i])
                                            .font(.system(size: 12, design: .monospaced))
                                            .frame(maxWidth: .infinity, alignment: .leading)
                                    }
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .frame(minHeight: 180)
                    }

                    Button("Clear log") { store.clearLog() }
                        .font(.footnote)
                }
                .padding()
            }
            .navigationTitle("Build")
        }
    }

    private func row(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(label).foregroundStyle(.secondary).frame(width: 110, alignment: .leading)
            Text(value).frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    // MARK: - Settings tab

    private var settingsTab: some View {
        NavigationStack {
            Form {
                Section("Builder server") {
                    TextField("http://192.168.1.10:8080", text: $store.builderURL)
                        .autocapitalization(.none)
                        .disableAutocorrection(true)
                        .keyboardType(.URL)
                    Text("The machine that runs the builder server (your Windows PC). It needs Rust + trunk. See the README in the zip.")
                        .font(.caption).foregroundStyle(.secondary)
                    Button("Test builder connection") { Task { await testBuilder() } }
                        .disabled(store.builderURL.isEmpty)
                }

                Section("FTP - Hostek") {
                    TextField("Host", text: $store.ftpHost)
                        .autocapitalization(.none).disableAutocorrection(true)
                    TextField("Username", text: $store.ftpUsername)
                        .autocapitalization(.none).disableAutocorrection(true)
                    HStack {
                        Text("Port")
                        Spacer()
                        TextField("21", value: $store.ftpPort, format: .number)
                            .keyboardType(.numberPad)
                            .multilineTextAlignment(.trailing)
                    }
                    Text("Kid projects deploy under /public_html/kids/ - change the deploy folder on the Build tab if you want somewhere else.")
                        .font(.caption).foregroundStyle(.secondary)
                }

                Section("FTP password") {
                    Text(store.hasSavedPassword
                         ? "Saved on this phone (Keychain). Builds use it without asking."
                         : "Not saved yet. Enter it once below, or tap Build and you will be asked.")
                        .font(.caption).foregroundStyle(.secondary)
                    SecureField("FTP password", text: $sheetPassword)
                    Toggle("Remember password on this phone", isOn: $store.rememberPassword)
                    HStack {
                        Button("Save password") { savePasswordFromSettings() }
                            .disabled(sheetPassword.isEmpty)
                        Spacer()
                        Button("Forget saved password", role: .destructive) {
                            KeychainService.delete(account: store.ftpUsername)
                            store.log("Saved FTP password removed from Keychain.")
                            store.objectWillChange.send()
                        }
                        .disabled(!store.hasSavedPassword)
                    }
                    Button("Test FTP login") { Task { await testFTP() } }
                        .disabled(!store.hasSavedPassword)
                }

                Section("About") {
                    Text("Kid Builder v1.0.0 - MikeGyver Studio\nColin and Luan build real Yew/WASM web apps from tap blocks. The FTP password stays in the iPhone Keychain and is never sent to the builder.")
                        .font(.caption).foregroundStyle(.secondary)
                }
            }
            .navigationTitle("Settings")
        }
    }

    // MARK: - Password sheet (first build, or password never saved)

    private var passwordSheet: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Enter the FTP password for \(store.ftpUsername). It is saved in the iPhone Keychain, and future builds will use it without asking. A grown-up types this part.")
                        .font(.subheadline)
                    SecureField("FTP password", text: $sheetPassword)
                    Toggle("Remember on this phone", isOn: $sheetRemember)
                }
                Section {
                    Button("Build & Deploy") {
                        let password = sheetPassword
                        let remember = sheetRemember
                        sheetPassword = ""
                        showPasswordSheet = false
                        Task { await performBuild(password: password, savePassword: remember) }
                    }
                    .disabled(sheetPassword.isEmpty)
                    Button("Cancel", role: .cancel) { showPasswordSheet = false }
                }
            }
            .navigationTitle("FTP password")
        }
    }

    // MARK: - Build flow

    private func startBuild() {
        guard let project = store.selectedProject else {
            store.buildStatus = "Pick a project first."
            return
        }
        guard BuilderService.normalisedURL(store.builderURL) != nil else {
            store.buildStatus = "Set the builder server address in Settings first."
            store.log("Build stopped: no builder URL.")
            return
        }
        _ = project
        if let saved = KeychainService.load(account: store.ftpUsername) {
            Task { await performBuild(password: saved, savePassword: false) }
        } else {
            sheetRemember = store.rememberPassword
            showPasswordSheet = true
        }
    }

    private func performBuild(password: String, savePassword: Bool) async {
        guard let builderURL = BuilderService.normalisedURL(store.builderURL),
              let project = store.selectedProject else { return }
        store.buildPhase = .building
        store.buildStatus = "Sending blocks to the builder..."
        store.clearLog()
        store.log("Build started for \(project.name). Builder: \(builderURL.absoluteString)")
        store.log("Deploy target: \(store.ftpUsername) @ \(store.ftpHost):\(store.ftpPort)\(project.deployPath)")

        if savePassword && store.rememberPassword {
            if KeychainService.save(password: password, account: store.ftpUsername) {
                store.log("FTP password saved in Keychain.")
            } else {
                store.log("Warning: could not save the FTP password - this build still uses it once.")
            }
        } else if savePassword {
            store.log("Password used once (Remember is off).")
        }

        do {
            // Step 1 - the server turns the blocks into Yew files and
            // builds them with Trunk. The deploy folder goes with the
            // request: the server validates and normalises it and
            // echoes it back, and this build uploads to exactly that
            // echoed folder.
            let response = try await BuilderService.buildBlocks(
                baseURL: builderURL, projectName: project.name,
                blocks: project.blocks, deployPath: project.deployPath)
            store.log("Build succeeded. Server log:")
            for line in response.log.split(separator: "\n") { store.log(String(line)) }
            store.log("Built \(response.files.count) files.")
            if let echoed = response.deployPath, !echoed.isEmpty, echoed != project.deployPath {
                store.updateDeployPath(echoed)
                store.log("Deploy folder normalised to \(echoed).")
            }
            store.log("Deploying to \(project.deployPath) - folders that do not exist yet will be created.")

            // Step 2 - upload from this phone over FTP.
            store.buildPhase = .uploading
            store.buildStatus = "Uploading to FTP..."
            let built: [(path: String, data: Data)] = response.files.compactMap { file in
                guard let data = file.data else { return nil }
                return (file.path, data)
            }
            guard !built.isEmpty else { throw BuildFlowError.emptyBuild }
            let client = FTPClient(host: store.ftpHost, port: store.ftpPort,
                                   username: store.ftpUsername, password: password)
            let remoteDir = project.deployPath
            let uploaded = try await Task.detached(priority: .userInitiated) {
                try client.upload(files: built, remoteDir: remoteDir) { progress in
                    Task { @MainActor in
                        store.buildStatus = "Uploading \(progress.currentFile) (\(progress.done)/\(progress.total))..."
                    }
                }
            }.value
            for line in uploaded { store.log(line) }

            store.buildPhase = .done
            store.buildStatus = "Deployed. Live at \(project.siteURL)"
            store.lastDeployURL = project.siteURL
            store.log("Done. Live at \(project.siteURL)")
        } catch {
            store.buildPhase = .failed
            store.buildStatus = error.localizedDescription
            store.log("FAILED: \(error.localizedDescription)")
        }
    }

    private func savePasswordFromSettings() {
        guard !sheetPassword.isEmpty else { return }
        if KeychainService.save(password: sheetPassword, account: store.ftpUsername) {
            store.log("FTP password saved in Keychain.")
            store.buildStatus = "Password saved."
        } else {
            store.log("Could not save the FTP password.")
        }
        sheetPassword = ""
        store.objectWillChange.send()
    }

    private func testBuilder() async {
        guard let url = BuilderService.normalisedURL(store.builderURL) else {
            store.buildStatus = "Enter a builder URL first."
            return
        }
        store.buildStatus = "Checking builder..."
        do {
            let health = try await BuilderService.checkHealth(baseURL: url)
            store.buildStatus = health.ok
                ? "Builder OK (\(health.trunk ?? "trunk version unknown"))."
                : "Builder answered but reported: \(health.error ?? "unknown error")"
            store.log("Builder check: \(store.buildStatus)")
        } catch {
            store.buildStatus = "Builder check failed: \(error.localizedDescription)"
            store.log("Builder check failed: \(error.localizedDescription)")
        }
    }

    private func testFTP() async {
        guard let password = KeychainService.load(account: store.ftpUsername) else {
            store.buildStatus = "Save the FTP password first."
            return
        }
        store.buildStatus = "Testing FTP login..."
        let client = FTPClient(host: store.ftpHost, port: store.ftpPort,
                               username: store.ftpUsername, password: password)
        do {
            try await Task.detached(priority: .userInitiated) { try client.testLogin() }.value
            store.buildStatus = "FTP login OK."
            store.log("FTP login test OK.")
        } catch {
            store.buildStatus = "FTP login failed: \(error.localizedDescription)"
            store.log("FTP login test failed: \(error.localizedDescription)")
        }
    }

    enum BuildFlowError: LocalizedError {
        case emptyBuild
        var errorDescription: String? {
            "The builder returned no files. Check the build log above."
        }
    }
}

// MARK: - Block editor

/// Editor for one block in the selected project.
///
/// Every kind shows only its own simple fields: text fields, a
/// stepper for the timer, a note picker for piano, three answer
/// fields plus a correct-answer picker for quiz questions. A picture
/// block shows its photo (or a placeholder) and two buttons: Take
/// photo (camera when the phone has one) and Choose from Photos.
/// Photos are downscaled to 320x240 JPEG before they are stored -
/// see PhotoHelper - so a project file never holds a full-size photo.
struct BlockEditorView: View {
    let blockIndex: Int
    @EnvironmentObject private var store: KidStore

    @State private var block: KidBlock?
    @State private var showPhotoPicker = false
    @State private var photoPickerItem: PhotosPickerItem?
    @State private var showCamera = false
    @State private var cameraAvailable = false

    var body: some View {
        Form {
            if let block {
                switch block {
                case .title(let text):
                    Section("Title") {
                        TextField("Title", text: binding(text, { .title(text: $0) }))
                            .autocapitalization(.sentences)
                        Text("The big words at the top of your page.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .words(let text):
                    Section("Words") {
                        TextField("Words", text: binding(text, { .words(text: $0) }), axis: .vertical)
                            .lineLimit(4...)
                            .autocapitalization(.sentences)
                        Text("A paragraph on your page.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .picture(let base64jpeg, let caption):
                    Section("Photo") {
                        if let image = PhotoHelper.image(fromBase64: base64jpeg) {
                            Image(uiImage: image)
                                .resizable()
                                .scaledToFit()
                                .frame(maxHeight: 240)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                        } else {
                            Text("No photo yet. Take one or pick one below.")
                                .font(.subheadline).foregroundStyle(.secondary)
                        }
                        TextField("Caption", text: binding(caption, { .picture(base64jpeg: base64jpeg, caption: $0) }))
                            .autocapitalization(.sentences)
                        Button("Take a photo") { showCamera = true }
                            .disabled(!cameraAvailable)
                        Button("Choose from Photos") { showPhotoPicker = true }
                        Text("Photos are made small (320x240) before they are saved, so your project stays fast.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .button(let label, let action):
                    Section("Button") {
                        TextField("Button words", text: binding(label, { .button(label: $0, action: action) }))
                            .autocapitalization(.sentences)
                        Picker("When tapped, it should...", selection: Binding(
                            get: { action },
                            set: { block = .button(label: label, action: $0); save() })) {
                            ForEach(KidBlock.ButtonAction.allCases, id: \.self) { a in
                                Text(a.label).tag(a)
                            }
                        }
                    }
                case .counter(let label):
                    Section("Counter") {
                        TextField("What are you counting?", text: binding(label, { .counter(label: $0) }))
                            .autocapitalization(.sentences)
                        Text("Visitors tap to count: stars, flights, claps.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .rocket:
                    Section("Rocket") {
                        Text("A rocket that flies when the Launch button is pressed. Add a Button block with the Launch action to fire it.")
                            .font(.subheadline)
                    }
                case .piano(let note):
                    Section("Piano note") {
                        Picker("Note", selection: Binding(
                            get: { note },
                            set: { block = .piano(note: $0); save() })) {
                            ForEach(["C", "D", "E", "F", "G", "A", "B"], id: \.self) { n in
                                Text(n).tag(n)
                            }
                        }
                        .pickerStyle(.segmented)
                        Text("One block plays one note. Stack seven blocks for the whole scale.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .quiz(let question, let answers, let correctIndex):
                    Section("Quiz question") {
                        TextField("Question", text: binding(question, { .quiz(question: $0, answers: answers, correctIndex: correctIndex) }))
                            .autocapitalization(.sentences)
                        ForEach(0..<3, id: \.self) { i in
                            TextField("Answer \(i + 1)", text: Binding(
                                get: { answers.indices.contains(i) ? answers[i] : "" },
                                set: { var a = answers; while a.count <= i { a.append("") }; a[i] = $0; block = .quiz(question: question, answers: a, correctIndex: correctIndex); save() }))
                        }
                        Picker("Right answer", selection: Binding(
                            get: { correctIndex },
                            set: { block = .quiz(question: question, answers: answers, correctIndex: $0); save() })) {
                            ForEach(0..<3, id: \.self) { i in
                                Text("Answer \(i + 1)").tag(i)
                            }
                        }
                        Text("Exactly three answers. Pick which one is right.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .timer(let seconds):
                    Section("Timer") {
                        Stepper("\(seconds) seconds", value: Binding(
                            get: { seconds },
                            set: { block = .timer(seconds: $0); save() }),
                            in: 5...120, step: 5)
                        Text("Counts down on your page, then rings.")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                case .sstv:
                    Section("Space sound (SSTV)") {
                        Text("This block turns your photo into space sound - the Robot 36 sound astronauts use to send photos from the Space Station - and can turn space sound back into a photo. On your finished page there is a button to download the sound as a WAV file, and a place to drop a WAV file to see the photo inside it.")
                            .font(.subheadline)
                    }
                }
            }
        }
        .navigationTitle(block?.displayName ?? "Block")
        .navigationBarTitleDisplayMode(.inline)
        .photosPicker(isPresented: $showPhotoPicker, selection: $photoPickerItem, matching: .images)
        .onChange(of: photoPickerItem) { _, item in
            guard let item else { return }
            Task {
                if let data = try? await item.loadTransferable(type: Data.self),
                   let image = UIImage(data: data),
                   let base64 = PhotoHelper.downscaledJPEGBase64(from: image),
                   case .picture(_, let caption) = block {
                    block = .picture(base64jpeg: base64, caption: caption)
                    save()
                }
                photoPickerItem = nil
            }
        }
        .sheet(isPresented: $showCamera) {
            CameraPicker { image in
                if let base64 = PhotoHelper.downscaledJPEGBase64(from: image),
                   case .picture(_, let caption) = block {
                    block = .picture(base64jpeg: base64, caption: caption)
                    save()
                }
            }
        }
        .onAppear {
            block = store.selectedProject?.blocks.indices.contains(blockIndex) == true
                ? store.selectedProject?.blocks[blockIndex] : nil
            cameraAvailable = UIImagePickerController.isSourceTypeAvailable(.camera)
        }
    }

    /// A text binding that writes the edited block back to the store
    /// on every keystroke.
    private func binding(_ value: String, _ make: @escaping (String) -> KidBlock) -> Binding<String> {
        Binding(get: { value }, set: { block = make($0); save() })
    }

    private func save() {
        guard let block else { return }
        store.updateBlock(at: blockIndex, to: block)
    }
}

// MARK: - Camera picker

/// UIImagePickerController wrapped for SwiftUI: the camera sheet.
///
/// PhotosPicker covers the photo library; this one covers the camera
/// itself, which PhotosPicker cannot do.
struct CameraPicker: UIViewControllerRepresentable {
    var onPhoto: (UIImage) -> Void

    func makeUIViewController(context: Context) -> UIImagePickerController {
        let picker = UIImagePickerController()
        picker.sourceType = .camera
        picker.delegate = context.coordinator
        return picker
    }

    func updateUIViewController(_ uiViewController: UIImagePickerController, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator(onPhoto: onPhoto) }

    final class Coordinator: NSObject, UIImagePickerControllerDelegate, UINavigationControllerDelegate {
        let onPhoto: (UIImage) -> Void

        init(onPhoto: @escaping (UIImage) -> Void) { self.onPhoto = onPhoto }

        func imagePickerController(
            _ picker: UIImagePickerController,
            didFinishPickingMediaWithInfo info: [UIImagePickerController.InfoKey: Any]
        ) {
            picker.dismiss(animated: true)
            if let image = info[.originalImage] as? UIImage {
                onPhoto(image)
            }
        }

        func imagePickerControllerDidCancel(_ picker: UIImagePickerController) {
            picker.dismiss(animated: true)
        }
    }
}
