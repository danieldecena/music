// Clicks the point x,y, then types Control-Option-Shift-Command-C, the Key Command assigned to
// "Apply Region Chords to Chord Track" in Logic. Logic only acts on it after a real click on the
// region and with real modifier key presses (found 2026-11-18); accessibility and posted events
// did nothing. The pointer goes back where it was.
// Usage: logic_keys <x> <y>
import CoreGraphics
import Foundation

let x = Double(CommandLine.arguments[1])!, y = Double(CommandLine.arguments[2])!
let src = CGEventSource(stateID: .hidSystemState)
let back = CGEvent(source: nil)!.location
let p = CGPoint(x: x, y: y)
CGWarpMouseCursorPosition(p)
usleep(100_000)
for t in [CGEventType.leftMouseDown, .leftMouseUp] {
    CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: p, mouseButton: .left)!.post(tap: .cghidEventTap)
    usleep(60_000)
}
CGWarpMouseCursorPosition(back)
usleep(300_000)

func post(_ key: CGKeyCode, _ down: Bool, _ flags: CGEventFlags) {
    let e = CGEvent(keyboardEventSource: src, virtualKey: key, keyDown: down)!
    e.flags = flags
    e.post(tap: .cghidEventTap)
    usleep(40_000)
}
let mods: [(CGKeyCode, CGEventFlags)] = [(59, .maskControl), (58, .maskAlternate), (56, .maskShift), (55, .maskCommand)]
var f: CGEventFlags = []
for (k, fl) in mods { f.insert(fl); post(k, true, f) }
post(8, true, f)
post(8, false, f)
for (k, fl) in mods.reversed() { f.remove(fl); post(k, false, f) }
print("typed")
