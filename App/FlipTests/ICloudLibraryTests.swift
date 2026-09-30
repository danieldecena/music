import Foundation
import Testing
@testable import Flip

@Suite("iCloud container claim")
struct ICloudLibraryTests {
    // The known-BAD input the simulator actually produces: no account signed in,
    // so `url(forUbiquityContainerIdentifier:)` would return nil for a reason
    // that says nothing about the container.
    @Test("no iCloud account reads as noAccount, not as a missing container")
    func noAccount() {
        #expect(ICloudLibrary.status(hasAccount: false, container: nil) == .noAccount)
    }

    // And the same nil with an account behind it, which IS a fault.
    @Test("signed in with an unresolved container is a claim failure")
    func claimFailed() {
        #expect(ICloudLibrary.status(hasAccount: true, container: nil) == .claimFailed)
    }

    // The known-GOOD input. Without this the suite could not tell a working
    // detector from one that never returns .ready.
    @Test("a resolved container reports its Documents directory")
    func ready() throws {
        let root = URL(filePath: "/Users/home/Library/Mobile Documents/iCloud~com~danieldecena~flip")
        let s = ICloudLibrary.status(hasAccount: true, container: root)
        #expect(s == .ready(root.appending(path: "Documents")))
    }

    // The path the Mac half writes into. `icloud_container()` in
    // lib/music-core.sh resolves to .../Documents and publish_to_icloud puts
    // Tracks/<track>/ beneath it; if this side stopped appending Documents the
    // two would silently address different directories.
    @Test("the ready path is the one the Mac publishes into")
    func agreesWithTheMac() throws {
        let root = URL(filePath: "/tmp/iCloud~com~danieldecena~flip")
        guard case .ready(let docs) = ICloudLibrary.status(hasAccount: true, container: root)
        else { Issue.record("expected .ready"); return }
        #expect(docs.lastPathComponent == "Documents")
    }

    @Test("the container id matches the entitlement")
    func containerID() {
        #expect(ICloudLibrary.containerID == "iCloud.com.danieldecena.flip")
    }
}
