import urwid
import logging

from .constants import VISIBILITY_OPTIONS

logger = logging.getLogger(__name__)


class EditBox(urwid.AttrWrap):
    def __init__(self):
        edit = urwid.Edit(multiline=True, allow_tab=True)
        return super().__init__(edit, "editbox", "editbox_focused")


class Button(urwid.AttrWrap):
    def __init__(self, *args, **kwargs):
        button = urwid.Button(*args, **kwargs)
        padding = urwid.Padding(button, width=len(args[0]) + 4)
        return super().__init__(padding, "button", "button_focused")

    def set_label(self, *args, **kwargs):
        self.original_widget.original_widget.set_label(*args, **kwargs)
        self.original_widget.width = len(args[0]) + 4


class StatusComposer(urwid.Frame):
    """
    UI for compose and posting a status message.
    """
    signals = ["close", "post"]

    def __init__(self):
        self.content_caption = urwid.Text("Status message")
        self.content_edit = EditBox()

        self.cw_caption = urwid.Text("Content warning")
        self.cw_edit = None
        self.cw_add_button = Button("Add content warning",
            on_press=self.add_content_warning)
        self.cw_remove_button = Button("Remove content warning",
            on_press=self.remove_content_warning)

        self.visibility = "public"
        self.visibility_button = Button("Visibility: {}".format(self.visibility),
            on_press=self.choose_visibility)

        self.post_button = Button("Post", on_press=self.post)
        self.cancel_button = Button("Cancel", on_press=self.close)

        contents = list(self.generate_list_items())
        logger.info(contents)
        self.walker = urwid.SimpleListWalker(contents)
        self.listbox = urwid.ListBox(self.walker)
        return super().__init__(self.listbox)

    def generate_list_items(self):
        yield self.content_caption
        yield self.content_edit
        yield urwid.Divider()

        if self.cw_edit:
            yield self.cw_caption
            yield self.cw_edit
            yield urwid.Divider()
            yield self.cw_remove_button
        else:
            yield self.cw_add_button

        yield self.visibility_button
        yield self.post_button
        yield self.cancel_button

    def refresh(self):
        self.walker = urwid.SimpleListWalker(list(self.generate_list_items()))
        self.listbox.body = self.walker

    def choose_visibility(self, *args):
        list_items = [urwid.Text("Choose status visibility:")]
        for visibility, caption, description in VISIBILITY_OPTIONS:
            text = "{} - {}".format(caption, description)
            button = Button(text, on_press=self.set_visibility, user_data=visibility)
            list_items.append(button)

        self.walker = urwid.SimpleListWalker(list_items)
        self.listbox.body = self.walker

        # Initially focus currently chosen visibility
        focus_map = {v[0]: n + 1 for n, v in enumerate(VISIBILITY_OPTIONS)}
        focus = focus_map.get(self.visibility, 1)
        self.walker.set_focus(focus)

    def set_visibility(self, widget, visibility):
        self.visibility = visibility
        self.visibility_button.set_label("Visibility: {}".format(self.visibility))
        self.refresh()
        self.walker.set_focus(7 if self.cw_edit else 4)

    def add_content_warning(self, button):
        self.cw_edit = EditBox()
        self.refresh()
        self.walker.set_focus(4)

    def remove_content_warning(self, button):
        self.cw_edit = None
        self.refresh()
        self.walker.set_focus(3)

    def set_error_message(self, msg):
        self.footer = urwid.Text(("footer_message_error", msg))

    def clear_error_message(self):
        self.footer = None

    def post(self, button):
        self.clear_error_message()

        # Don't lstrip content to avoid removing intentional leading whitespace
        # However, do strip both sides to check if there is any content there
        content = self.content_edit.edit_text.rstrip()
        content = None if not content.strip() else content

        warning = self.cw_edit.edit_text.rstrip() if self.cw_edit else ""
        warning = None if not warning.strip() else warning

        if not content:
            self.set_error_message("Cannot post an empty message")
            return

        self._emit("post", content, warning, self.visibility)

    def close(self, button):
        self._emit("close")
