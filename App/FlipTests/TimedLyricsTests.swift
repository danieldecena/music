import Testing
@testable import Flip

@Suite("Timed lyrics")
struct TimedLyricsTests {
    let sample = """
        [ar:Frank Ocean]
        [ti:Ivy]
        [00:02.32]Back then
        [00:04.62]No matter what I did
        [00:06.70]My waves wouldn't dip back then
        """

    @Test("metadata tags are dropped, lyric lines kept")
    func dropsMetadata() {
        #expect(TimedLyrics.parse(sample).count == 3)
    }

    @Test("mm:ss.cc parses to seconds")
    func parsesSeconds() {
        #expect(abs(TimedLyrics.parse(sample)[0].start - 2.32) < 1e-6)
    }

    @Test("the timestamp is stripped from the text")
    func stripsStamp() {
        #expect(TimedLyrics.parse(sample)[0].text == "Back then")
    }

    @Test("a line ends where the next begins")
    func endsAtNext() {
        let end = try! #require(TimedLyrics.parse(sample)[0].end)
        #expect(abs(end - 4.62) < 1e-6)
    }

    @Test("the last line has no end, because the parser cannot know the duration")
    func lastHasNoEnd() {
        #expect(TimedLyrics.parse(sample).last?.end == nil)
    }

    @Test("minutes carry, so 2:05.50 is 125.5s not 205.5s")
    func minutesCarry() {
        #expect(abs(TimedLyrics.parse("[02:05.50]late")[0].start - 125.5) < 1e-6)
    }

    @Test("one line with two timestamps yields two rows")
    func repeatedChorus() {
        let r = TimedLyrics.parse("[00:10.00][01:20.00]same words")
        #expect(r.count == 2)
        #expect(r[0].start == 10.0)
        #expect(r[1].start == 80.0)
    }

    @Test("rows come back in time order even when the file is not")
    func sorts() {
        let r = TimedLyrics.parse("[00:09.00]second\n[00:01.00]first")
        #expect(r.map(\.text) == ["first", "second"])
    }

    @Test("a tie on the timestamp keeps file order, matching Python's stable sort")
    func tieKeepsFileOrder() {
        // Scripts/lyrics.py:timed_lrc relies on Python's list.sort being
        // stable. Swift's Array.sort makes no such guarantee, so this pins
        // that the port's explicit index tiebreak reproduces it.
        let r = TimedLyrics.parse("[00:05.00]alpha\n[00:05.00]beta")
        #expect(r.map(\.text) == ["alpha", "beta"])
    }

    @Test("degenerate inputs return empty rather than crashing")
    func degenerate() {
        #expect(TimedLyrics.parse("").isEmpty)
        #expect(TimedLyrics.parse("[ar:Nobody]\n").isEmpty)
        #expect(TimedLyrics.parse("no timestamp here").isEmpty)
        #expect(TimedLyrics.parse("[00:04.00]   ").isEmpty)
    }
}
