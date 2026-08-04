"""Small interactive session selector used by the command-line interface."""

import curses
import os
import sys

def curses_menu(stdscr, options, title="Select a Claude Code session:"):
    curses.curs_set(0) # Hide cursor
    curses.start_color()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_CYAN) # Highlighted item
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK) # Regular item
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK) # Header

    current_idx = 0
    max_y, max_x = stdscr.getmaxyx()

    while True:
        stdscr.erase()
        
        # Header
        stdscr.addstr(0, 0, title[:max_x-1], curses.color_pair(3) | curses.A_BOLD)
        stdscr.addstr(1, 0, "Use ↑ / ↓ arrow keys to navigate, ENTER to select, 'q' to quit:", curses.color_pair(2))
        stdscr.addstr(2, 0, "-" * min(max_x - 1, 75), curses.color_pair(2))

        visible_start = max(0, current_idx - (max_y - 6) // 2)
        visible_end = min(len(options), visible_start + max_y - 5)

        for i in range(visible_start, visible_end):
            line_y = 3 + (i - visible_start)
            opt_text = options[i]
            
            # Format text line
            prefix = "❯ " if i == current_idx else "  "
            full_line = f"{prefix}{opt_text}"
            full_line = full_line[:max_x-1].ljust(max_x-1)

            if i == current_idx:
                stdscr.addstr(line_y, 0, full_line, curses.color_pair(1) | curses.A_BOLD)
            else:
                stdscr.addstr(line_y, 0, full_line, curses.color_pair(2))

        stdscr.refresh()

        key = stdscr.getch()
        if key in (curses.KEY_UP, ord('k')):
            current_idx = (current_idx - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord('j')):
            current_idx = (current_idx + 1) % len(options)
        elif key in (10, 13, curses.KEY_ENTER):
            return current_idx
        elif key in (27, ord('q')): # ESC or q
            return None

def select_option(options, title):
    if not sys.stdout.isatty():
        # Fallback for non-interactive / piped environments
        return 0
    try:
        return curses.wrapper(curses_menu, options, title)
    except Exception:
        # Fallback
        return 0
