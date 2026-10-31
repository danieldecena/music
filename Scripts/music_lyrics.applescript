-- Read or write one library track's Lyrics field.
-- osascript music_lyrics.applescript get <persistent ID>
-- osascript music_lyrics.applescript set <persistent ID> <text file>
-- Music stores line breaks as carriage returns, so callers compare after
-- normalizing newlines.
on run argv
	set verb to item 1 of argv
	set pid to item 2 of argv
	tell application "Music"
		set t to (first file track of library playlist 1 whose persistent ID is pid)
		if verb is "get" then return lyrics of t
		set newText to read POSIX file (item 3 of argv) as «class utf8»
		set lyrics of t to newText
		return lyrics of t
	end tell
end run
