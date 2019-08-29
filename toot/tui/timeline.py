import logging
import urwid
import webbrowser

from toot.utils import format_content

from .utils import highlight_hashtags
from .widgets import SelectableText, SelectableColumns

logger = logging.getLogger("toot")


class Timeline(urwid.Columns):
    """
    Displays a list of statuses to the left, and status details on the right.
    """
    signals = [
        "status_focused",
        "status_activated",
        "next",
    ]

    def __init__(self, tui, statuses):
        self.tui = tui
        self.statuses = statuses

        self.status_list = self.build_status_list(statuses)
        self.status_details = StatusDetails(statuses[0])

        # Maps status ID to its index in the list
        self.status_index_map = {
            status.id: n for n, status in enumerate(statuses)
        }

        super().__init__([
            ("weight", 40, self.status_list),
            ("weight", 60, self.status_details),
        ], dividechars=1)

    def build_status_list(self, statuses):
        items = [self.build_list_item(status) for status in statuses]
        walker = urwid.SimpleFocusListWalker(items)
        urwid.connect_signal(walker, "modified", self.status_focused)
        return urwid.ListBox(walker)

    def build_list_item(self, status):
        item = StatusListItem(status)
        urwid.connect_signal(item, "click", self.status_activated)
        return urwid.AttrMap(item, None, focus_map={
            "blue": "green_selected",
            "green": "green_selected",
            "yellow": "green_selected",
            None: "green_selected",
        })

    def get_focused_status(self):
        return self.statuses[self.status_list.body.focus]

    def status_activated(self, *args):
        """Called when a status is clicked, or Enter is pressed."""
        status = self.get_focused_status()
        self._emit("status_activated", [status])

    def status_focused(self):
        """Called when the list focus switches to a new status"""
        status = self.get_focused_status()
        self.draw_status_details(status)

        index = self.status_list.body.focus
        count = len(self.statuses)
        self._emit("status_focused", [status, index, count])

    def draw_status_details(self, status):
        self.status_details = StatusDetails(status)
        self.contents[1] = self.status_details, ("weight", 50, False)

    def keypress(self, size, key):
        # If down is pressed on last status in list emit a signal to load more.
        # TODO: Consider pre-loading statuses earlier
        command = self._command_map[key]
        if command in [urwid.CURSOR_DOWN, urwid.CURSOR_PAGE_DOWN]:
            index = self.status_list.body.focus + 1
            count = len(self.statuses)
            if index >= count:
                self._emit("next")

        if key in ("b", "B"):
            status = self.get_focused_status()
            self.tui.async_toggle_reblog(status)
            return

        if key in ('c', 'C'):
            self.tui.show_compose()
            return

        if key in ("f", "F"):
            status = self.get_focused_status()
            self.tui.async_toggle_favourite(status)
            return

        if key in ("v", "V"):
            status = self.get_focused_status()
            webbrowser.open(status.data["url"])
            return

        if key in ("u", "U"):
            status = self.get_focused_status()
            self.tui.show_status_source(status)
            return

        return super().keypress(size, key)

    def add_status(self, status):
        self.statuses.append(status)
        self.status_index_map[status.id] = len(self.statuses) - 1
        self.status_list.body.append(self.build_list_item(status))

    def prepend_status(self, status):
        self.statuses.insert(0, status)
        # Need to rebuild the map, there has to be a better way
        self.status_index_map = {
            status.id: n for n, status in enumerate(self.statuses)
        }
        self.status_list.body.insert(0, self.build_list_item(status))

        if self.status_list.body.focus == 0:
            self.draw_status_details(status)

    def add_statuses(self, statuses):
        for status in statuses:
            self.add_status(status)

    def update_status(self, status):
        """Overwrite status in list with the new instance and redraw."""
        index = self.status_index_map[status.id]
        assert self.statuses[index].id == status.id

        # Update internal status list
        self.statuses[index] = status

        # Redraw list item
        self.status_list.body[index] = self.build_list_item(status)

        # Redraw status details if status is focused
        if index == self.status_list.body.focus:
            self.draw_status_details(status)


class StatusDetails(urwid.Pile):
    def __init__(self, status):
        widget_list = list(self.content_generator(status))
        return super().__init__(widget_list)

    def content_generator(self, status):
        if status.data["reblog"]:
            boosted_by = status.data["account"]["display_name"]
            yield ("pack", urwid.Text(("gray", "♺ {} boosted".format(boosted_by))))
            yield ("pack", urwid.AttrMap(urwid.Divider("-"), "gray"))

        if status.author.display_name:
            yield ("pack", urwid.Text(("green", status.author.display_name)))

        yield ("pack", urwid.Text(("yellow", status.author.account)))
        yield ("pack", urwid.Divider())

        for line in format_content(status.data["content"]):
            yield ("pack", urwid.Text(highlight_hashtags(line)))

        if status.data["card"]:
            yield ("pack", urwid.Divider())
            yield ("pack", self.build_card(status.data["card"]))

        # Push things to bottom
        yield ("weight", 1, urwid.SolidFill(" "))
        yield ("pack", urwid.Text([
            ("cyan_bold", "B"), ("cyan", "oost"), " | ",
            ("cyan_bold", "F"), ("cyan", "avourite"), " | ",
            ("cyan_bold", "V"), ("cyan", "iew"), " | ",
            ("cyan", "So"), ("cyan_bold", "u"), ("cyan", "rce"), " | ",
            ("cyan_bold", "H"), ("cyan", "elp"), " ",
        ]))

    def card_generator(self, card):
        yield urwid.Text(("green", card["title"].strip()))
        if card["author_name"]:
            yield urwid.Text(["by ", ("yellow", card["author_name"].strip())])
        yield urwid.Text("")
        if card["description"]:
            yield urwid.Text(card["description"].strip())
            yield urwid.Text("")
        yield urwid.Text(("link", card["url"]))

    def build_card(self, card):
        contents = list(self.card_generator(card))
        card = urwid.Pile(contents)
        card = urwid.Padding(card, left=1, right=1)
        return urwid.LineBox(card)


class StatusListItem(SelectableColumns):
    def __init__(self, status):
        created_at = status.created_at.strftime("%Y-%m-%d %H:%M")
        favourited = ("yellow", "★") if status.favourited else " "
        reblogged = ("yellow", "⤶") if status.reblogged else " "

        return super().__init__([
            ("pack", SelectableText(("blue", created_at), wrap="clip")),
            ("pack", urwid.Text(" ")),
            urwid.Text(("green", status.account), wrap="clip"),
            ("pack", urwid.Text(" ")),
            ("pack", urwid.Text(favourited)),
            ("pack", urwid.Text(" ")),
            ("pack", urwid.Text(reblogged)),
        ])
