import SwiftUI

@main
struct KidBuilderApp: App {
    @StateObject private var store = KidStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
