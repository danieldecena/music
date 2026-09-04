import Foundation

/// Everything the three tabs read, assembled once after analysis.
///
/// The tabs hold no logic — they draw this. Keeping the assembly in one place
/// means the loop scorer runs once rather than per tab switch.
struct TrackAnalysis {
    let bpm: Double
    let key: String
    let duration: Double
    let bars: [Bar]
    let sections: [TrackSection]
    let activity: [ActivitySample]
    let lyrics: [LyricLine]
    let loops: [LoopCandidate]
    let grid: BarGrid

    init(bpm: Double, key: String, duration: Double, bars: [Bar],
         sections: [TrackSection], activity: [ActivitySample], lyrics: [LyricLine]) {
        self.bpm = bpm
        self.key = key
        self.duration = duration
        self.bars = bars
        self.sections = sections
        self.activity = activity
        self.lyrics = lyrics
        self.grid = BarGrid(bars: bars)
        self.loops = LoopScorer
            .score(bars: bars, sections: sections, activity: activity, nBars: 4)
            .sorted { $0.score > $1.score }
    }

    /// The instrument families MusicUnderstanding reports. Exactly four, always:
    /// `other` is the catch-all, so guitar, keys, synths and strings share it.
    var instruments: [String] {
        ["drum", "bass", "other", "vocal"]
    }

    func samples(for instrument: String) -> [ActivitySample] {
        activity.filter { $0.instrument == instrument }
    }

    /// The loudest this family reaches anywhere, so a lane sitting near zero
    /// reads as measured-quiet rather than as a lane that failed to draw.
    func peak(for instrument: String) -> Double {
        samples(for: instrument).map(\.level).max() ?? 0
    }
}
