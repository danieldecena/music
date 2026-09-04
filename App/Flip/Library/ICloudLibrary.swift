import Foundation

/// Where a container claim can end up.
///
/// `url(forUbiquityContainerIdentifier:)` is documented to return one `nil` for
/// two different worlds -- "iCloud storage is unavailable for the current user
/// or device" and "the container could not be located" -- and only the second
/// is a defect worth chasing. Collapsing them into one `nil` would report a
/// simulator with nobody signed in exactly the way it reports a container that
/// is genuinely missing from the App ID.
///
/// `ubiquityIdentityToken` separates them: documented as `nil` precisely when
/// iCloud is unavailable or there is no logged-in user, and cheap enough to
/// read on the main thread.
enum ContainerStatus: Equatable {
    /// Nobody is signed in to iCloud here. Says nothing about the container.
    case noAccount
    /// Signed in, and the container still did not resolve. This one is a fault.
    case claimFailed
    /// The container's `Documents` directory, which is what the Mac writes into.
    case ready(URL)

    var label: String {
        switch self {
        case .noAccount:   return "no iCloud account on this device"
        case .claimFailed: return "signed in, but \(ICloudLibrary.containerID) did not resolve"
        case .ready(let u): return "ready \(u.path)"
        }
    }
}

enum ICloudLibrary {
    static let containerID = "iCloud.com.danieldecena.flip"

    /// The decision, with both FileManager reads lifted out as arguments so
    /// every branch is testable on a machine with no iCloud account.
    ///
    /// `Documents` is appended here rather than at each call site because it is
    /// the half the Mac agrees on: `icloud_container()` in `lib/music-core.sh`
    /// resolves to `.../iCloud~com~danieldecena~flip/Documents`, and
    /// `publish_to_icloud` writes `Tracks/<track>/` beneath it.
    static func status(hasAccount: Bool, container: URL?) -> ContainerStatus {
        guard hasAccount else { return .noAccount }
        guard let container else { return .claimFailed }
        return .ready(container.appending(path: "Documents"))
    }

    /// Claims the container. The first call extends the app's sandbox to include
    /// it, which is what makes the directory exist for the account -- including
    /// on the Mac, where nothing local can create it (`mkdir` under
    /// `~/Library/Mobile Documents` is refused; only `bird` may).
    ///
    /// Apple's page carries an Important: do not call this from the main thread,
    /// because setting up iCloud takes a nontrivial amount of time. Hence the
    /// detached task here rather than a note asking callers to remember.
    static func claim() async -> ContainerStatus {
        guard FileManager.default.ubiquityIdentityToken != nil else { return .noAccount }
        return await Task.detached(priority: .utility) {
            status(hasAccount: true,
                   container: FileManager.default
                       .url(forUbiquityContainerIdentifier: containerID))
        }.value
    }
}
