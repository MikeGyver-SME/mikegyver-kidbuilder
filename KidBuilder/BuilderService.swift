import Foundation

/// Talks to the Kid Builder builder server (the same server family as
/// YewBuilder's server.py, extended with block endpoints).
///
/// Why a server at all: an iPhone cannot run cargo or trunk - there is
/// no Rust toolchain on iOS. So the phone sends a project's blocks to
/// a small server you run yourself (your Windows PC, over your home
/// LAN or over Tailscale), the server turns the blocks into the five
/// Yew files and runs `trunk build --release`, and it sends the
/// finished dist/ files back as base64. The phone then uploads those
/// files to FTP itself, so the FTP password never leaves the phone.
///
/// API:
///   GET  /health            -> {"ok": true, "trunk": "trunk 0.22.1"}
///   POST /generate-blocks   -> {"project_name", "blocks": [...]}
///                            <- {"success": bool, "log": "...",
///                                "files": [{"path", "content"}]}
///   POST /build-blocks     -> {"project_name", "blocks": [...],
///                              "deploy_path": "/public_html/kids/x"}
///                            <- {"success": bool, "log": "...",
///                                "files": [{"path", "content_base64"}],
///                                "deploy_path": "..."}
///
/// /generate-blocks only makes the source files - it never builds and
/// never deploys. That is the endpoint behind the Code tab ("See my
/// code"): the Rust a kid sees is the real file the server generated
/// from their blocks, never a guess made up on the phone. If the
/// server cannot be reached, the Code tab says so plainly instead of
/// showing invented code.
enum BuilderService {
    struct SourceFile: Codable {
        let path: String
        let content: String
    }

    struct BlocksRequest: Codable {
        let project_name: String
        let blocks: [KidBlock]
        let deploy_path: String?
    }

    struct GenerateResponse: Codable {
        let success: Bool
        let log: String
        let files: [SourceFile]

        /// The generated src/main.rs, if the server returned one.
        var mainRs: String? {
            files.first { $0.path == "src/main.rs" }?.content
        }
    }

    struct BuiltFile: Codable {
        let path: String
        let content_base64: String

        var data: Data? { Data(base64Encoded: content_base64) }
    }

    struct BuildResponse: Codable {
        let success: Bool
        let log: String
        let files: [BuiltFile]
        /// The deploy folder, normalised by the server ("/" for the site
        /// root). Nil when the server is an older version that does not
        /// echo it - then the phone keeps the folder it sent.
        let deploy_path: String?

        var deployPath: String? { deploy_path }
    }

    struct HealthResponse: Codable {
        let ok: Bool
        let trunk: String?
        let error: String?
    }

    enum BuilderError: LocalizedError {
        case badURL(String)
        case httpStatus(Int, String)
        case noData
        case buildFailed(String)
        case generateFailed(String)

        var errorDescription: String? {
            switch self {
            case .badURL(let u): return "Builder URL is not a valid http(s) URL: \(u)"
            case .httpStatus(let code, let body):
                return "Builder returned HTTP \(code). \(body.prefix(300))"
            case .noData: return "Builder returned no data."
            case .buildFailed(let log): return "Build failed:\n\(log)"
            case .generateFailed(let log): return "Could not get the code:\n\(log)"
            }
        }
    }

    /// Normalise a user-typed builder address: add http:// when no scheme,
    /// strip a trailing slash.
    static func normalisedURL(_ raw: String) -> URL? {
        var text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return nil }
        if !text.lowercased().hasPrefix("http://") && !text.lowercased().hasPrefix("https://") {
            text = "http://" + text
        }
        while text.hasSuffix("/") { text.removeLast() }
        return URL(string: text)
    }

    static func checkHealth(baseURL: URL) async throws -> HealthResponse {
        let url = baseURL.appendingPathComponent("health")
        var request = URLRequest(url: url)
        request.timeoutInterval = 15
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw BuilderError.noData }
        guard (200..<300).contains(http.statusCode) else {
            throw BuilderError.httpStatus(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        return try JSONDecoder().decode(HealthResponse.self, from: data)
    }

    /// Ask the server to turn blocks into source files (no build).
    static func generateBlocks(
        baseURL: URL, projectName: String, blocks: [KidBlock]
    ) async throws -> GenerateResponse {
        let url = baseURL.appendingPathComponent("generate-blocks")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 60
        request.httpBody = try JSONEncoder().encode(
            BlocksRequest(project_name: projectName, blocks: blocks, deploy_path: nil))
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw BuilderError.noData }
        guard (200..<300).contains(http.statusCode) else {
            throw BuilderError.httpStatus(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        let decoded = try JSONDecoder().decode(GenerateResponse.self, from: data)
        guard decoded.success else { throw BuilderError.generateFailed(decoded.log) }
        return decoded
    }

    /// Send the blocks, wait for the server to generate the Yew files
    /// and build them (first builds can take a couple of minutes while
    /// cargo fetches crates), return dist/ files.
    static func buildBlocks(
        baseURL: URL, projectName: String, blocks: [KidBlock], deployPath: String?
    ) async throws -> BuildResponse {
        let url = baseURL.appendingPathComponent("build-blocks")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.timeoutInterval = 300
        request.httpBody = try JSONEncoder().encode(
            BlocksRequest(project_name: projectName, blocks: blocks, deploy_path: deployPath))
        let (data, response) = try await URLSession.shared.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw BuilderError.noData }
        guard (200..<300).contains(http.statusCode) else {
            throw BuilderError.httpStatus(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
        let decoded = try JSONDecoder().decode(BuildResponse.self, from: data)
        guard decoded.success else { throw BuilderError.buildFailed(decoded.log) }
        return decoded
    }
}
