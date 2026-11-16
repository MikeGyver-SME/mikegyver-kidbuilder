import Foundation

/// The block model for Kid Builder.
///
/// A project is a name plus an ordered list of blocks. Blocks are the
/// only thing a kid edits: big tap targets, text fields, steppers and
/// pickers - never raw Rust. The phone sends the blocks as JSON to the
/// builder server (see BuilderService), and the server turns them into
/// the five real Yew files, builds them with Trunk, and sends the
/// finished site back. There is no Rust generator in this app on
/// purpose: the server is the one place that knows how to turn blocks
/// into code, so the phone and the server can never disagree.
///
/// Wire shape (what the server sees): each block is one JSON object
/// with a "kind" string and the fields for that kind, for example:
///   {"kind": "title", "text": "My Rocket Launch"}
///   {"kind": "quiz", "question": "1 + 3 = ?", "answers": ["3", "4", "5"], "correct_index": 1}
///   {"kind": "picture", "base64jpeg": "...", "caption": "My photo"}
/// Photos are stored small on purpose: at most 320x240 JPEG at
/// quality 0.7, so a project file stays small and a build stays fast.
enum KidBlock: Codable, Equatable {
    case title(text: String)
    case words(text: String)
    case picture(base64jpeg: String, caption: String)
    case button(label: String, action: ButtonAction)
    case counter(label: String)
    case rocket
    case piano(note: String)
    case quiz(question: String, answers: [String], correctIndex: Int)
    case timer(seconds: Int)
    case sstv

    /// What a button does when a visitor taps it on the finished site.
    enum ButtonAction: String, Codable, CaseIterable {
        case count = "count"
        case rocket = "rocket"
        case sound = "sound"

        var label: String {
            switch self {
            case .count: return "Count one more"
            case .rocket: return "Launch the rocket"
            case .sound: return "Play a sound"
            }
        }
    }

    /// The "kind" string on the wire, and the name shown in the editor.
    var kind: String {
        switch self {
        case .title: return "title"
        case .words: return "words"
        case .picture: return "picture"
        case .button: return "button"
        case .counter: return "counter"
        case .rocket: return "rocket"
        case .piano: return "piano"
        case .quiz: return "quiz"
        case .timer: return "timer"
        case .sstv: return "sstv"
        }
    }

    /// Short name shown in the block list.
    var displayName: String {
        switch self {
        case .title: return "Title"
        case .words: return "Words"
        case .picture: return "Photo"
        case .button: return "Button"
        case .counter: return "Counter"
        case .rocket: return "Rocket"
        case .piano: return "Piano note"
        case .quiz: return "Quiz question"
        case .timer: return "Timer"
        case .sstv: return "Space sound (SSTV)"
        }
    }

    /// One-line summary shown under the block name in the list.
    var summary: String {
        switch self {
        case .title(let text): return text.isEmpty ? "No title yet" : text
        case .words(let text): return text.isEmpty ? "No words yet" : text
        case .picture(_, let caption): return caption.isEmpty ? "A photo" : caption
        case .button(let label, let action): return "\(label) - \(action.label)"
        case .counter(let label): return label.isEmpty ? "Counter" : label
        case .rocket: return "Press Launch and it flies"
        case .piano(let note): return "Note \(note)"
        case .quiz(let question, _, _): return question.isEmpty ? "No question yet" : question
        case .timer(let seconds): return "\(seconds) seconds"
        case .sstv: return "Photo to space sound, and back"
        }
    }

    /// SF Symbol for the block list. No emoji anywhere in the app.
    var systemImage: String {
        switch self {
        case .title: return "textformat.size"
        case .words: return "text.alignleft"
        case .picture: return "photo"
        case .button: return "button.programmable"
        case .counter: return "number"
        case .rocket: return "paperplane"
        case .piano: return "pianokeys"
        case .quiz: return "questionmark.circle"
        case .timer: return "timer"
        case .sstv: return "waveform"
        }
    }

    /// A fresh block of each kind, for the Add block menu.
    static func blank(kind: String) -> KidBlock {
        switch kind {
        case "title": return .title(text: "My App")
        case "words": return .words(text: "Hello, world!")
        case "picture": return .picture(base64jpeg: "", caption: "My photo")
        case "button": return .button(label: "Tap me", action: .count)
        case "counter": return .counter(label: "Count")
        case "rocket": return .rocket
        case "piano": return .piano(note: "C")
        case "quiz": return .quiz(question: "1 + 3 = ?", answers: ["3", "4", "5"], correctIndex: 1)
        case "timer": return .timer(seconds: 10)
        case "sstv": return .sstv
        default: return .words(text: "")
        }
    }

    /// Every kind a kid can add, in menu order.
    static let allKinds: [String] = [
        "title", "words", "picture", "button", "counter",
        "rocket", "piano", "quiz", "timer", "sstv",
    ]

    // MARK: - Codable (kind discriminator)

    private enum CodingKeys: String, CodingKey {
        case kind, text, base64jpeg, caption, label, action
        case note, question, answers, correctIndex, seconds
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let kind = try c.decode(String.self, forKey: .kind)
        switch kind {
        case "title":
            self = .title(text: try c.decode(String.self, forKey: .text))
        case "words":
            self = .words(text: try c.decode(String.self, forKey: .text))
        case "picture":
            self = .picture(
                base64jpeg: try c.decode(String.self, forKey: .base64jpeg),
                caption: try c.decode(String.self, forKey: .caption))
        case "button":
            self = .button(
                label: try c.decode(String.self, forKey: .label),
                action: try c.decode(ButtonAction.self, forKey: .action))
        case "counter":
            self = .counter(label: try c.decode(String.self, forKey: .label))
        case "rocket":
            self = .rocket
        case "piano":
            self = .piano(note: try c.decode(String.self, forKey: .note))
        case "quiz":
            self = .quiz(
                question: try c.decode(String.self, forKey: .question),
                answers: try c.decode([String].self, forKey: .answers),
                correctIndex: try c.decode(Int.self, forKey: .correctIndex))
        case "timer":
            self = .timer(seconds: try c.decode(Int.self, forKey: .seconds))
        case "sstv":
            self = .sstv
        default:
            throw DecodingError.dataCorruptedError(
                forKey: .kind, in: c,
                debugDescription: "Unknown block kind: \(kind)")
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.container(keyedBy: CodingKeys.self)
        try c.encode(kind, forKey: .kind)
        switch self {
        case .title(let text):
            try c.encode(text, forKey: .text)
        case .words(let text):
            try c.encode(text, forKey: .text)
        case .picture(let base64jpeg, let caption):
            try c.encode(base64jpeg, forKey: .base64jpeg)
            try c.encode(caption, forKey: .caption)
        case .button(let label, let action):
            try c.encode(label, forKey: .label)
            try c.encode(action, forKey: .action)
        case .counter(let label):
            try c.encode(label, forKey: .label)
        case .rocket:
            break
        case .piano(let note):
            try c.encode(note, forKey: .note)
        case .quiz(let question, let answers, let correctIndex):
            try c.encode(question, forKey: .question)
            try c.encode(answers, forKey: .answers)
            try c.encode(correctIndex, forKey: .correctIndex)
        case .timer(let seconds):
            try c.encode(seconds, forKey: .seconds)
        case .sstv:
            break
        }
    }
}

/// One kid project: a name, a web folder, and its blocks.
///
/// The slug is the folder name under /kids/ on the site, so
/// "my-rocket-launch" lives at mikegyver-studio.si/kids/my-rocket-launch/
/// Slugs are lowercase letters, digits and hyphens only.
struct KidProject: Codable, Identifiable, Equatable {
    var id: UUID
    var name: String
    var slug: String
    var description: String
    var deployPath: String
    var blocks: [KidBlock]

    init(id: UUID = UUID(), name: String, slug: String, description: String,
         deployPath: String, blocks: [KidBlock]) {
        self.id = id
        self.name = name
        self.slug = slug
        self.description = description
        self.deployPath = deployPath
        self.blocks = blocks
    }

    /// The public link for this project, derived from its deploy folder.
    /// Hostek layout: public_html IS the web root, so a leading
    /// public_html segment is dropped from the link only (the FTP
    /// upload path itself is unchanged).
    var siteURL: String {
        let trimmed = deployPath.trimmingCharacters(in: .whitespaces)
        var parts = trimmed.split(separator: "/").map(String.init)
        if parts.first?.lowercased() == "public_html" { parts.removeFirst() }
        let path = parts.joined(separator: "/")
        if path.isEmpty { return "https://mikegyver-studio.si/" }
        return "https://mikegyver-studio.si/\(path)/"
    }
}
