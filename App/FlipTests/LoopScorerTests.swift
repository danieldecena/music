import Testing
@testable import Flip

@Suite("Loop scorer parity with Scripts/regions.py")
struct LoopScorerTests {
    // An 8-bar grid at 2s per bar. Vocal loud over the first half, silent after.
    // Two sections meeting at 8.0s, so windows crossing that point straddle.
    // Sections are FIXED here on purpose: macOS reports 3 sections for the
    // bundled clip and iOS reports 2, so device-derived sections would test the
    // platform difference instead of the port. Do not replace these with
    // whatever the device produced.
    let bars = (0...8).map { Bar(idx: $0, t: Double($0) * 2.0) }
    let sections = [TrackSection(start: 0.0, end: 8.0), TrackSection(start: 8.0, end: 16.0)]
    let activity = [
        ActivitySample(instrument: "vocal", start: 0.0, end: 8.0, level: 0.8),
        ActivitySample(instrument: "vocal", start: 8.0, end: 16.0, level: 0.0),
        ActivitySample(instrument: "drum", start: 0.0, end: 16.0, level: 0.6),
    ]

    var scored: [LoopCandidate] {
        LoopScorer.score(bars: bars, sections: sections, activity: activity, nBars: 4)
    }

    @Test("one window per bar that has four bars after it")
    func windowCount() {
        #expect(scored.count == 5)
    }

    @Test("scores match the Python exactly")
    func parity() {
        let expected = [0.200000, 0.300000, 0.450000, 0.600000, 1.000000]
        for (got, want) in zip(scored, expected) {
            #expect(abs(got.score - want) < 1e-9,
                    "bar \(got.startBar): got \(got.score), want \(want)")
        }
    }

    @Test("a window inside one section is not penalised")
    func contained() {
        // bars 0-4 == 0.0-8.0s, exactly section one. vocal 0.8 -> 1-0.8 = 0.2.
        #expect(abs(scored[0].score - 0.2) < 1e-9)
    }

    @Test("a window crossing a section boundary takes the straddle penalty")
    func straddles() {
        // bars 1-5 == 2.0-10.0s, crossing 8.0. vocal mean 0.6 -> 0.4 * 0.75.
        #expect(abs(scored[1].score - 0.3) < 1e-9)
    }

    @Test("levels are duration-weighted, not a plain average")
    func weighted() {
        // bars 1-5 spans 6s of vocal 0.8 and 2s of 0.0 -> 0.6, not 0.4.
        #expect(abs(scored[1].instruments["vocal"]! - 0.6) < 1e-9)
    }

    @Test("every instrument present is reported, not just the one scored on")
    func reportsAll() {
        #expect(abs(scored[0].instruments["drum"]! - 0.6) < 1e-9)
    }

    @Test("too few bars for one window returns empty rather than crashing")
    func tooFewBars() {
        let short = [Bar(idx: 0, t: 0), Bar(idx: 1, t: 2)]
        #expect(LoopScorer.score(bars: short, sections: sections,
                                 activity: activity, nBars: 4).isEmpty)
    }

    @Test("no bars at all returns empty")
    func noBars() {
        #expect(LoopScorer.score(bars: [], sections: [],
                                 activity: [], nBars: 4).isEmpty)
    }
}
