-- Find local file tracks, or read or write one track's Lyrics field.
-- osascript music_lyrics.applescript find <title fragment>   (id TAB title TAB artist per line)
-- osascript music_lyrics.applescript get <persistent ID>
-- osascript music_lyrics.applescript set <persistent ID> <text file>
-- Music stores line breaks as carriage returns, so callers compare after
-- normalizing newlines.
on run argv
	set verb to item 1 of argv
	tell application "Music"
		if verb is "find" then
			set out to ""
			repeat with t in (every file track of library playlist 1 whose name contains (item 2 of argv))
				set out to out & (persistent ID of t) & tab & (name of t) & tab & (artist of t) & linefeed
			end repeat
			return out
		end if
		set t to (first file track of library playlist 1 whose persistent ID is (item 2 of argv))
		if verb is "get" then return lyrics of t
		set newText to read POSIX file (item 3 of argv) as «class utf8»
		set lyrics of t to newText
		return lyrics of t
	end tell
end run
