import Foundation

/// The five starter projects every kid starts with.
///
/// Each one is a real project a kid can open, change, and deploy -
/// not a demo that disappears. The first three are the ones Mike
/// picked: Rocket Launch, Counting Stars Quiz, and Piano Notes. The
/// fourth adds the camera, and the fifth is the SSTV one: a photo
/// becomes space sound (Robot 36, the same mode the ISS uses), and
/// space sound can become a photo again.
///
/// Quiz answers are kept kid-simple: three choices, one right answer.
/// The counting-stars questions all use the same idea Colin already
/// knows from his morning show - adding odd numbers makes square
/// numbers: 1 + 3 = 4, 1 + 3 + 5 = 9, 1 + 3 + 5 + 7 = 16.
enum KidProjects {
    static func starters() -> [KidProject] {
        [rocketLaunch, countingStarsQuiz, pianoNotes, takeAPhoto, photoToSpaceSound]
    }

    static let rocketLaunch = KidProject(
        name: "My Rocket Launch",
        slug: "my-rocket-launch",
        description: "Press Launch and watch your rocket fly.",
        deployPath: "/public_html/kids/my-rocket-launch",
        blocks: [
            .title(text: "My Rocket Launch"),
            .words(text: "Hi, I am Colin! Press the button and watch my rocket fly up into the sky."),
            .rocket,
            .button(label: "Launch", action: .rocket),
            .counter(label: "Flights"),
        ]
    )

    static let countingStarsQuiz = KidProject(
        name: "Counting Stars Quiz",
        slug: "counting-stars-quiz",
        description: "A quiz about odd numbers making square numbers.",
        deployPath: "/public_html/kids/counting-stars-quiz",
        blocks: [
            .title(text: "Counting Stars Quiz"),
            .words(text: "Odd numbers are magic. Add them up and you get square numbers! Try the quiz."),
            .quiz(question: "What is 1?", answers: ["0", "1", "2"], correctIndex: 1),
            .quiz(question: "1 + 3 = ?", answers: ["3", "4", "5"], correctIndex: 1),
            .quiz(question: "1 + 3 + 5 = ?", answers: ["8", "9", "10"], correctIndex: 1),
            .quiz(question: "1 + 3 + 5 + 7 = ?", answers: ["15", "16", "17"], correctIndex: 1),
            .quiz(question: "1 + 3 + 5 + 7 + 9 = ?", answers: ["24", "25", "26"], correctIndex: 1),
            .counter(label: "Stars"),
        ]
    )

    static let pianoNotes = KidProject(
        name: "Piano Notes",
        slug: "piano-notes",
        description: "Tap the keys and play a tune.",
        deployPath: "/public_html/kids/piano-notes",
        blocks: [
            .title(text: "Piano Notes"),
            .words(text: "Hi, I am Colin! I play piano. Tap a note to hear it, then press Play a tune to hear them all together."),
            .piano(note: "C"),
            .piano(note: "D"),
            .piano(note: "E"),
            .piano(note: "F"),
            .piano(note: "G"),
            .piano(note: "A"),
            .piano(note: "B"),
            .button(label: "Play a tune", action: .sound),
        ]
    )

    static let takeAPhoto = KidProject(
        name: "Take a Photo",
        slug: "take-a-photo",
        description: "Take a photo with the camera and put it on your own web page.",
        deployPath: "/public_html/kids/take-a-photo",
        blocks: [
            .title(text: "Take a Photo"),
            .words(text: "Tap the photo block below to take a photo with the camera, or pick one from your photos. Then build it and your photo is on the web!"),
            .picture(base64jpeg: "", caption: "My photo"),
            .words(text: "Your photo is made small before it is saved, so it loads fast for everyone."),
        ]
    )

    static let photoToSpaceSound = KidProject(
        name: "Photo to Space Sound",
        slug: "photo-to-space-sound",
        description: "Turn your photo into space sound, and space sound back into a photo.",
        deployPath: "/public_html/kids/photo-to-space-sound",
        blocks: [
            .title(text: "Photo to Space Sound"),
            .words(text: "Turn your photo into space sound, and turn space sound back into a photo. Robot 36."),
            .words(text: "Astronauts on the Space Station send photos this way. Your photo becomes a funny squeaky sound, and the sound can become a photo again. Ask a grown-up to help you listen for the Space Station on the radio."),
            .picture(base64jpeg: "", caption: "My photo for space"),
            .sstv,
        ]
    )
}
