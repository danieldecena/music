import Testing
@testable import Flip

@Suite("Bar grid")
struct BarGridTests {
    let even = BarGrid(bars: (0...8).map { Bar(idx: $0, t: Double($0) * 2.0) })

    // A grid that stretches, as Apple's tracking reports for a real track:
    // Ivy runs 2.08s per bar early and 2.95s by the outro.
    let drift = BarGrid(bars: [
        Bar(idx: 0, t: 0.0), Bar(idx: 1, t: 2.0), Bar(idx: 2, t: 4.2),
        Bar(idx: 3, t: 6.6), Bar(idx: 4, t: 9.2), Bar(idx: 5, t: 12.0),
    ])

    @Test("a downbeat maps to its own index")
    func downbeat() {
        #expect(abs(even.barAt(4.0) - 2.0) < 1e-9)
    }

    @Test("a time between downbeats interpolates")
    func interpolates() {
        #expect(abs(even.barAt(5.0) - 2.5) < 1e-9)
    }

    @Test("a drifting grid is read directly, not assumed even")
    func readsDrift() {
        // 5.4s is halfway between bar 2 (4.2) and bar 3 (6.6).
        #expect(abs(drift.barAt(5.4) - 2.5) < 1e-9)
    }

    @Test("past the last downbeat it extrapolates rather than clamping")
    func extrapolates() {
        // The last gap is 2.0s, so 18.0s is one bar past bar 8.
        #expect(abs(even.barAt(18.0) - 9.0) < 1e-9)
    }

    @Test("time(atBar:) inverts barAt")
    func roundTrips() {
        for t in [0.0, 3.7, 5.4, 11.9] {
            #expect(abs(drift.time(atBar: drift.barAt(t)) - t) < 1e-6)
        }
    }

    @Test("an empty grid does not crash and reports a zero span")
    func empty() {
        let g = BarGrid(bars: [])
        #expect(g.firstBar == 0)
        #expect(g.lastBar == 0)
        #expect(g.barAt(5.0) == 0)
    }

    @Test("a one-bar grid degrades to that bar rather than dividing by zero")
    func single() {
        let g = BarGrid(bars: [Bar(idx: 3, t: 5.0)])
        #expect(g.barAt(5.0) == 3.0)
        #expect(g.barAt(99.0) == 3.0)
    }
}
