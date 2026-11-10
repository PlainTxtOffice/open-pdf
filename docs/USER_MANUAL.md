---
last_updated: 2026-11-10
version: 0.4.2
product_versions:
  windows: "1.0.1"
  linux: "0.1.0"
  mac_os: "0.1.0"
---

# User Manual

## 1. Overview

Open PDF is a desktop PDF viewer and light editor. The repository currently
documents source-install workflows and Nuitka builds for Windows and Linux.
The application provides a GUI for opening, viewing,
searching, lightly editing, printing, and saving PDF files, and it also
accepts an optional PDF path on launch.

Verified from: `README.md`; `platform/windows/pyproject.toml`
(`project.scripts`); `platform/windows/open_pdf/main.py` (`main`);
`platform/windows/open_pdf/gui/views/root_window/window.py` (`MainWindow`)

## 2. System Requirements

| Requirement | Verified Value | Notes | Verified from |
| --- | --- | --- | --- |
| Release-build operating system | Windows; Linux target: Ubuntu 24.04 x86-64 | Linux implementation and workflow are present; its first hosted build and runtime verification are pending. | README.md; platform/windows/scripts/nuitka/onefile.ps1; platform/linux/scripts/build.py; .github/workflows/linux-build.yml |
| Python for source install | Windows: 3.12 or newer; Linux: 3.14 | Required when running from source. | platform/windows/pyproject.toml; platform/linux/pyproject.toml [project.requires-python] |
| GUI dependency | PySide6 >=6.9,<7 | Required for source installs. | platform/windows/pyproject.toml [project.dependencies] |
| PDF engine | PyMuPDF >=1.26,<2 | Required for source installs. | platform/windows/pyproject.toml [project.dependencies] |
| OCR engine | Tesseract, optional | The OCR actions stay disabled unless a Tesseract backend is found on the system. | platform/windows/open_pdf/adapters/ocr/tesseract.py [create_tesseract_ocr_backend]; platform/windows/open_pdf/main.py [_create_default_ocr_backend] |
| Hardware requirements | Unknown. | No CPU, RAM, GPU, or display minimums are documented in the allowed sources. | README.md; platform/windows/pyproject.toml |

## 3. Installation & Setup

### macOS Setup

The initial macOS implementation provides the Qt viewer and light editor,
Finder document opening, standard Command shortcuts, and Keychain password
storage. See [macOS setup and build instructions](../platform/mac_os/README.md).
Its Python tests have been run on Windows; native Mac execution, packaging,
printing, and Keychain access remain unverified.

Settings use `~/Library/Application Support/Open PDF`, existing OCR results
use `~/Library/Caches/Open PDF/ocr`, and logs use `~/Library/Logs/Open PDF`.
Source and packaged launches use the same locations. The app does not store
passwords in JSON or write settings inside its application bundle.

Verified from: `platform/mac_os/pyproject.toml`;
`platform/mac_os/open_pdf/config/path_handler.py`;
`platform/mac_os/open_pdf/adapters/persistence/passwords.py`;
`platform/mac_os/open_pdf/gui/application.py`;
`platform/mac_os/scripts/open_pdf.spec`

### Linux Setup

The Linux implementation uses Python 3.14 and Qt. Its **Linux build** workflow
tests the application, builds a standalone directory, verifies PDF rendering,
and uploads a `.tar.gz` archive. Once published, run the workflow from GitHub's
Actions tab and download the `open-pdf-linux-x86_64` artifact after it succeeds.
The first hosted run is still pending.

Extract the archive, keep its files together, and launch `./open-pdf` from the
extracted folder. The archive bundles Python. It targets Ubuntu 24.04 x86-64
with X11 or XWayland; other distributions and native Wayland are not verified.

Preferences use `~/.config/open-pdf`, the OCR cache uses
`~/.cache/open-pdf/ocr`, and logs use `~/.local/state/open-pdf/logs`. Absolute
`XDG_CONFIG_HOME`, `XDG_CACHE_HOME`, and `XDG_STATE_HOME` overrides are honored.
Source launches use these same locations. Linux never stores data beside the
executable or migrates Windows folders.

Remembered passwords use the desktop Secret Service keyring. If the service is
unavailable or locked, manual password entry remains available; no plaintext
password fallback is written. To use OCR, install Tesseract and language packs
through your distribution's package manager.

See the [Linux guide](../platform/linux/README.md) for source installation,
system libraries, desktop registration, and build commands. The Windows
packaging and storage instructions below apply only to Windows.

Verified from: `platform/linux/pyproject.toml`;
`platform/linux/open_pdf/config/path_handler.py` (`xdg_directory`);
`platform/linux/open_pdf/adapters/persistence/passwords.py`
(`DocumentPasswordStore`); `platform/linux/scripts/build.py` (`main`);
`.github/workflows/linux-build.yml`

### Windows Build Setup

No prebuilt download is documented in this repository. To produce a Windows
executable, run one of the checked-in Nuitka build scripts. The two scripts
produce the two distributable shapes, and they differ in where the app keeps
its settings, logs, and caches.

| Script | Output | Storage location |
| --- | --- | --- |
| `onefile.ps1` | `platform/windows/build/onefile/open-pdf-<version>-portable.exe`, one self-contained file | Portable: an `open-pdf-data` folder beside the executable |
| `standalone.ps1` | `platform/windows/build/standalone/main.dist/open-pdf.exe`, with dependencies for the installer | Per-user: `%LOCALAPPDATA%\open-pdf` |
| `standalone-debug.ps1` | `platform/windows/build/standalone-debug/main.dist/open-pdf.exe`, with a console for troubleshooting | Per-user: `%LOCALAPPDATA%\open-pdf` |

1. From `platform/windows/`, run `./scripts/nuitka/onefile.ps1` for the
   portable build, or `./scripts/nuitka/standalone.ps1` for the directory an
   installer wraps. Both use `platform/windows/.venv` as the build interpreter.
1. Launch the produced executable.
1. Verify that the main window opens.
1. If no PDF is opened on launch, confirm that the empty state says `Open a PDF
   to begin.`

The portable build is selected by a `portable.marker` file that `onefile.ps1`
bundles into the build and `standalone.ps1` leaves out. Nothing at runtime
switches the mode, so an installed build cannot become portable by accident.
If the folder beside a portable executable is read-only, Open PDF stores its
data in `%LOCALAPPDATA%\open-pdf` instead and notes that in its log.

Copying a portable folder to another machine carries the pane layout, notes,
and OCR cache with it. Remembered PDF passwords do not travel: they are
protected against the Windows account that stored them, so they fail to
decrypt elsewhere and Open PDF simply prompts again.

Verified from: README.md; platform/windows/scripts/nuitka/onefile.ps1;
platform/windows/scripts/nuitka/standalone.ps1;
platform/windows/open_pdf/config/path_handler.py [IS_PORTABLE];
platform/windows/open_pdf/config/path_handler.py [resolve_storage];
platform/windows/open_pdf/config/path_handler.py [resolve_user_data_dir];
platform/windows/open_pdf/adapters/persistence/passwords.py
[DocumentPasswordStore];
platform/windows/open_pdf/gui/views/root_window/window.py
[_build_document_view]; platform/windows/tests/test_path_handler.py
[test_portable_storage_sits_beside_the_onefile_binary]

### Source Install Setup

1. Open a terminal in `platform/windows/` and create a virtual environment.
1. Install the project in editable mode.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e .
```

1. Start the app.

```powershell
open-pdf
```

1. Optionally open a PDF immediately at launch.

```powershell
open-pdf path/to/file.pdf
```

1. Verify that the application window opens successfully.

Verified from: README.md; platform/windows/pyproject.toml [project.scripts];
platform/windows/open_pdf/main.py [build_argument_parser];
platform/windows/open_pdf/main.py [main]

## 4. Using the Program in VS Code

### VS Code Workspace Workflow

1. Open the repository root as a VS Code workspace.
1. Open the integrated terminal in `platform/windows/`.
1. Install or update the editable source install if needed, then activate
   `.venv` so `open-pdf` is on the path.
1. Run `open-pdf` or `open-pdf path/to/file.pdf` from the terminal.
1. If Open PDF is already running, launching it again activates the existing
   window and can forward the requested PDF into that running instance.

Verified from: .vscode/settings.json; platform/windows/pyproject.toml
[project.scripts]; platform/windows/open_pdf/adapters/runtime/single_instance.py
[SingleInstanceCoordinator]; platform/windows/open_pdf/main.py
[build_argument_parser]

### VS Code Launch Support

No checked-in VS Code task file or launch configuration file is present, so the
verified way to start the app from VS Code is the integrated terminal.

Verified from: .vscode/tasks.json; .vscode/launch.json; .vscode/settings.json

## 5. VS Code Tasks

Not Applicable.
Verified from: .vscode/tasks.json

## 6. CLI Usage

| Command | Purpose | Behavior | Verified from |
| --- | --- | --- | --- |
| `open-pdf` | Start the desktop app without opening a file first. | The main window opens and shows the empty state until a PDF is opened. | platform/windows/pyproject.toml [project.scripts]; platform/windows/open_pdf/main.py [main]; platform/windows/open_pdf/gui/views/root_window/window.py [_build_document_view] |
| `open-pdf path/to/file.pdf` | Start the desktop app and request one PDF at launch. | The path is parsed as an optional positional argument and opened in the GUI. | platform/windows/open_pdf/main.py [build_argument_parser]; platform/windows/open_pdf/main.py [main]; platform/windows/open_pdf/gui/views/root_window/tabs/document_tabs.py [_open_path_in_tab] |

Additional CLI options beyond the optional PDF path are Unknown.
Verified from: platform/windows/open_pdf/main.py [build_argument_parser]

## 7. GUI Usage

### Opening PDFs and Managing Tabs

1. Use `File > Open` to choose a PDF from disk.
1. If a PDF is already open, opening a different file creates another tab.
1. If you try to open a PDF that is already open in another tab, Open PDF reuses
   the existing tab instead of creating a duplicate.
1. Drag a tab along the tab bar to reorder it. Each tab keeps its own page,
   zoom, notes, and search state.
1. Use `File > Close Tab`, `Ctrl+W`, or the close button on the tab itself to
   close the active tab.

Verified from: platform/windows/open_pdf/gui/views/root_window/window.py
[_choose_pdf];
platform/windows/open_pdf/gui/views/root_window/tabs/document_tabs.py
[_open_path_in_tab];
platform/windows/open_pdf/gui/views/root_window/tabs/document_tabs.py
[_close_current_tab]; platform/windows/open_pdf/gui/views/menus/file_menu.py
[populate_file_menu]; platform/windows/tests/test_app.py
[test_opening_second_document_creates_new_tab_and_preserves_first_state];
platform/windows/tests/test_app.py
[test_opening_existing_document_path_reuses_existing_tab];
platform/windows/tests/test_app.py
[test_drag_reordering_tabs_preserves_session_state]

### Moving Around a Document

1. Use the page number control on the tool bar to jump directly to a page.
1. Click a page in the page thumbnails pane to navigate there.
1. Click a bookmark in the bookmarks pane to jump through the document outline.
1. Click internal PDF links in the document view to jump to their destinations.
1. Click external PDF links to open them in the default browser.
1. Click a link that points at another local PDF to open that file in a new tab.
1. Use `View > Single Page View` to show only the current page in the document
   view. While this mode is on and the document view has focus, `Up` and `Down`
   move to the previous or next page.

Open PDF keeps a back and forward page history that records the scroll
position you were reading at, not just the page number, so returning to an
entry puts you back where you were. The history is maintained internally, but
its back and forward actions carry no menu item, tool bar button, or keyboard
shortcut in this version, so there is currently no way to trigger them from
the UI.

Verified from: platform/windows/open_pdf/gui/views/root_window/window.py
[_handle_page_selected];
platform/windows/open_pdf/gui/views/root_window/window.py [_go_back_history];
platform/windows/open_pdf/gui/views/root_window/window.py [_go_forward_history];
platform/windows/open_pdf/gui/views/root_window/window.py
[_set_single_page_view_enabled];
platform/windows/open_pdf/gui/views/root_window/window.py [eventFilter];
platform/windows/open_pdf/gui/views/menus/toolbars.py [add_history_actions];
platform/windows/open_pdf/gui/views/menus/view_menu.py [populate_view_menu];
platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py
[_handle_thumbnail_selected];
platform/windows/open_pdf/gui/views/root_window/navigation/page_links.py
[_handle_page_link_activated];
platform/windows/open_pdf/application/document/session.py
[record_history_position];
platform/windows/open_pdf/domains/document/pages/history.py [ScrollState];
platform/windows/tests/test_reader.py
[test_navigation_history_tracks_direct_page_jumps];
platform/windows/tests/test_reader.py
[test_history_restores_the_scroll_position_it_recorded];
platform/windows/tests/test_page_history.py
[test_go_back_restores_the_position_not_just_the_page];
platform/windows/tests/test_app.py
[test_clicking_internal_pdf_link_navigates_to_target_page];
platform/windows/tests/test_app.py
[test_clicking_pdf_uri_link_opens_external_browser];
platform/windows/tests/test_app.py
[test_clicking_pdf_file_link_opens_target_pdf_in_app];
platform/windows/tests/test_app.py
[test_single_page_view_shows_only_current_page];
platform/windows/tests/test_app.py
[test_single_page_view_uses_up_down_for_page_steps]

### Search and Zoom Controls

1. Press `Ctrl+F` to show the search bar.
1. Enter a query in the `Find` box. Results update as you type.
1. Use `Previous Match` and `Next Match` to move through results.
1. Press `Escape` or hide the search bar to clear the current query and matches.
1. Use `View > Actual Size`, `View > Fit Width`, or the `Fit Page` tool bar
   button to change zoom.
1. Use `Ctrl` plus the mouse wheel over the document view to zoom around the
   pointer.

Verified from: platform/windows/open_pdf/gui/views/menus/toolbars.py
[add_search_actions]; platform/windows/open_pdf/gui/views/menus/view_menu.py
[populate_view_menu]; platform/windows/open_pdf/gui/views/root_window/window.py
[_focus_search_input]; platform/windows/open_pdf/gui/views/root_window/window.py
[_hide_search_bar];
platform/windows/open_pdf/gui/views/rendering/zoom/interaction.py
[_zoom_to_actual_size];
platform/windows/open_pdf/gui/views/rendering/zoom/interaction.py
[_zoom_fit_width];
platform/windows/open_pdf/gui/views/rendering/zoom/interaction.py
[_zoom_fit_page];
platform/windows/open_pdf/gui/views/rendering/zoom/interaction.py
[_ctrl_wheel_zoom_target]; platform/windows/tests/test_app.py
[test_find_action_reveals_search_bar]; platform/windows/tests/test_app.py
[test_search_updates_as_user_types]; platform/windows/tests/test_app.py
[test_escape_hides_search_bar]; platform/windows/tests/test_app.py
[test_hide_search_bar_clears_query_and_matches];
platform/windows/tests/test_app.py
[test_ctrl_wheel_zoom_uses_smaller_increment_than_shortcut_zoom]

### Keyboard Shortcuts

| Shortcut | Action | Verified from |
| --- | --- | --- |
| `Ctrl+F` | Show the search bar and focus the `Find` box. | platform/windows/open_pdf/gui/views/menus/toolbars.py [add_search_actions] |
| `Ctrl+W` | Close the active document tab. | platform/windows/open_pdf/gui/views/menus/file_menu.py [add_file_menu_actions] |
| `Escape` | Hide the search bar while the `Find` box has focus. | platform/windows/open_pdf/gui/views/root_window/window.py [eventFilter] |
| `Up` / `Down` | Step to the previous or next page while `Single Page View` is on and the document view has focus. | platform/windows/open_pdf/gui/views/root_window/window.py [eventFilter] |
| `Ctrl` plus mouse wheel | Zoom the document view around the pointer. | platform/windows/open_pdf/gui/views/rendering/zoom/interaction.py [_ctrl_wheel_zoom_target] |

`Ctrl+F` and `Ctrl+W` are the only assigned key sequences. Page stepping,
zoom in and out, and history back and forward exist as actions without key
sequences in this version.

Verified from: platform/windows/open_pdf/gui/views/menus/toolbars.py
[build_toolbar]; platform/windows/tests/test_app.py
[test_find_is_the_only_remaining_keyboard_shortcut]

### Editing Page Content

1. Click `Edit PDF` on the tool bar to switch into `Mode: Edit PDF`.
1. Click and drag a rectangle over the page content you want to change.
1. Right-click the selection and choose `Remove Content`, or use `Edit > Remove
   Content`, to redact that region from the PDF.
1. Right-click the selection and choose `Replace Text...` to rewrite the text
   span the selection covers. The dialog opens pre-filled with the current text,
   and a longer replacement is shrunk so it still fits on one line.
1. `Replace Text...` needs the selection to land on a single editable text span.
   If the selection covers no editable text, Open PDF reports that no editable
   text was found.

Verified from: platform/windows/open_pdf/gui/views/menus/toolbars.py
[add_pdf_edit_actions]; platform/windows/open_pdf/gui/views/menus/edit_menu.py
[populate_edit_menu]; platform/windows/open_pdf/gui/views/rendering/selection.py
[_enter_pdf_edit_mode];
platform/windows/open_pdf/gui/views/rendering/selection.py
[_show_page_surface_context_menu];
platform/windows/open_pdf/gui/views/workflows/text_editing.py
[_remove_selected_text];
platform/windows/open_pdf/gui/views/workflows/text_editing.py
[_replace_selected_text];
platform/windows/open_pdf/application/document/session.py [replace_text_span];
platform/windows/open_pdf/adapters/document/pymupdf/content/editing.py
[replace_text_span];
platform/windows/open_pdf/gui/views/rendering/page_surface.py
[set_edit_selection_enabled]; platform/windows/tests/test_app.py
[test_edit_pdf_action_redacts_selected_rectangle];
platform/windows/tests/test_text_editing.py
[test_longer_replacement_shrinks_to_stay_on_one_line]

### Managing Pages

1. Use `Edit > Insert Blank Page Before` or `Edit > Insert Blank Page After` to
   add a blank page next to the current page. The new page copies the size of
   its neighbour rather than defaulting to Letter, and becomes the current page.
1. Select a page in the thumbnails pane, then use the arrow buttons above the
   thumbnail list (`Move page up` and `Move page down`) to move that page within
   the document.
1. Right-click a page thumbnail and choose `Rotate Right` to rotate that page
   clockwise.
1. Right-click a page thumbnail and choose `Delete Page` to remove a page after
   confirmation.

Page moves and insertions clear the current search results and rebuild the
bookmarks and thumbnails panes, because page numbering has shifted.

Verified from: platform/windows/open_pdf/gui/views/menus/edit_menu.py
[add_page_actions]; platform/windows/open_pdf/gui/views/root_window/window.py
[_insert_blank_page_at];
platform/windows/open_pdf/gui/views/root_window/window.py
[_move_current_page_by];
platform/windows/open_pdf/gui/views/root_window/window.py
[_build_page_move_button];
platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py
[_show_thumbnail_context_menu];
platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py
[_rotate_thumbnail_page];
platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py
[_delete_thumbnail_page];
platform/windows/open_pdf/application/document/session.py [insert_blank_page];
platform/windows/open_pdf/application/document/session.py [move_page];
platform/windows/open_pdf/domains/document/pages/reordering.py
[page_index_after_move]; platform/windows/tests/test_reader.py
[test_inserted_page_matches_the_neighbour_page_size];
platform/windows/tests/test_reader.py
[test_inserting_a_blank_page_shifts_the_following_pages];
platform/windows/tests/test_reader.py
[test_move_page_marks_document_dirty_and_keeps_moved_page_selected];
platform/windows/tests/test_app.py
[test_thumbnail_arrow_buttons_reorder_selected_page];
platform/windows/tests/test_app.py
[test_thumbnail_context_menu_can_delete_a_page];
platform/windows/tests/test_app.py
[test_thumbnail_context_menu_can_rotate_its_page]

### Saving, Renaming, and Printing

1. Use `Edit > Run OCR on Current Page` or `Edit > Run OCR on Document` when OCR
   is configured. Both actions are disabled while the document has unsaved
   changes.
1. Use `File > Save` to write supported in-place changes back to the currently
   opened file.
1. Use `File > Save As` to save a copy and switch the active document to that
   new file.
1. Use `File > Rename File` to write the document under a new name and remove
   the old file. If the chosen name already exists, Open PDF asks before
   replacing it, and a remembered password follows the document to its new path.
1. Use `File > Print` to open the print dialog. The app supports printing all
   pages, the current page, or a page range.
1. Use `File > Properties` to edit PDF Info Dictionary fields and raw XMP
   metadata.

Verified from: platform/windows/open_pdf/gui/views/menus/edit_menu.py
[add_ocr_actions]; platform/windows/open_pdf/gui/views/menus/file_menu.py
[populate_file_menu]; platform/windows/open_pdf/gui/views/root_window/window.py
[_save]; platform/windows/open_pdf/gui/views/root_window/window.py [_save_as];
platform/windows/open_pdf/gui/views/root_window/window.py [_refresh_actions];
platform/windows/open_pdf/gui/views/workflows/file_rename.py [_rename_file];
platform/windows/open_pdf/gui/views/workflows/file_rename.py
[_confirm_rename_file_overwrite];
platform/windows/open_pdf/gui/views/workflows/printing.py [_print_document];
platform/windows/open_pdf/gui/views/root_window/window.py
[_edit_document_properties]; platform/windows/tests/test_reader.py
[test_save_writes_changes_back_to_opened_file];
platform/windows/tests/test_app.py [test_save_as_switches_to_new_file];
platform/windows/tests/test_app.py [test_rename_file_replaces_old_path];
platform/windows/tests/test_app.py
[test_rename_file_can_overwrite_existing_destination];
platform/windows/tests/test_app.py
[test_file_menu_includes_print_action_and_triggers_handler];
platform/windows/tests/test_app.py
[test_print_document_honors_selected_page_range];
platform/windows/tests/test_app.py [test_properties_action_updates_pdf_metadata]

### Text Selection and Bookmark Editing

1. Use `Mode: Read` to browse the document and select text.
1. Select text either in the extracted text pane or directly on the page text
   overlay.
1. Use the context menu to `Copy`, `Select All`, or `Add Bookmark From
   Selection`.
1. Right-click an item in the bookmarks pane to `Rename Bookmark` or `Delete
   Bookmark`.

Verified from: platform/windows/open_pdf/gui/views/menus/view_menu.py
[add_mouse_mode_actions];
platform/windows/open_pdf/gui/views/rendering/selection.py
[_show_page_text_context_menu];
platform/windows/open_pdf/gui/views/rendering/selection.py
[_show_page_surface_context_menu];
platform/windows/open_pdf/gui/views/root_window/navigation/bookmarks.py
[_show_bookmark_context_menu];
platform/windows/open_pdf/gui/views/rendering/page_surface.py
[createStandardContextMenu]; platform/windows/tests/test_app.py
[test_text_selection_mode_updates_toolbar_indicator_and_page_overlay];
platform/windows/tests/test_app.py
[test_page_overlay_context_menu_includes_selection_actions];
platform/windows/tests/test_app.py
[test_bookmark_context_menu_can_rename_bookmark];
platform/windows/tests/test_app.py
[test_bookmark_context_menu_can_delete_bookmark]

### Layout and Pane Controls

1. Use the `View` menu to show or hide `Bookmarks`, `Thumbnails`, `Extracted
   Text`, or `Notes`.
1. Use `View > Bookmarks On Left` or `View > Thumbnails On Left` to swap which
   side pane appears on the left.
1. Drag the splitters between panes to resize them.
1. Pane visibility, mouse mode, and side-pane layout persist between launches.

Verified from: platform/windows/open_pdf/gui/views/menus/view_menu.py
[add_pane_actions]; platform/windows/open_pdf/gui/views/menus/view_menu.py
[add_side_pane_actions];
platform/windows/open_pdf/gui/views/root_window/persistence.py
[_restore_pane_visibility_settings];
platform/windows/open_pdf/gui/views/root_window/persistence.py
[_persist_pane_visibility_settings]; platform/windows/tests/test_app.py
[test_view_menu_toggles_panes]; platform/windows/tests/test_app.py
[test_pane_visibility_persists_between_windows];
platform/windows/tests/test_app.py [test_mouse_mode_persists_between_windows];
platform/windows/tests/test_app.py
[test_side_pane_layout_persists_between_windows]

### Document Notes

1. Type plain text in the `Notes` pane.
1. Use `File > Save` or `File > Save As` to persist the notes as an embedded
   `notes.txt` attachment inside the PDF.
1. Clear the pane and save to remove the embedded notes attachment.

Notes participate in the normal unsaved-changes workflow and travel with the PDF
rather than being stored in a separate sidecar file.

Verified from: platform/windows/open_pdf/application/document/session.py
[notes_text]; platform/windows/open_pdf/application/document/session.py
[update_notes];
platform/windows/open_pdf/adapters/document/pymupdf/content/attachments.py
[read_text_attachment];
platform/windows/open_pdf/adapters/document/pymupdf/content/attachments.py
[write_text_attachment];
platform/windows/open_pdf/gui/views/root_window/window.py
[_handle_notes_changed]; platform/windows/tests/test_reader.py
[test_clearing_document_notes_removes_embedded_attachment];
platform/windows/tests/test_app.py [test_notes_pane_edits_are_saved_inside_pdf]

### Help

Use `Help > About Open PDF` to show the About dialog.

Verified from: platform/windows/open_pdf/gui/views/menus/help/help_menu.py
[populate_help_menu];
platform/windows/open_pdf/gui/views/menus/help/about_open_pdf.py
[show_about_open_pdf_dialog]; platform/windows/tests/test_app.py
[test_file_menu_has_exit_and_help_menu_has_about]

## 8. Configuration

Open PDF does not expose a separate in-app settings screen. Where it keeps
runtime configuration depends on how it was built.

| Build | `data/` and `logs/` live under |
| --- | --- |
| Source checkout | `platform/windows/` in the repository |
| Portable (`onefile.ps1`) | `open-pdf-data` beside the executable |
| Portable, read-only folder | `%LOCALAPPDATA%\open-pdf` |
| Installed (`standalone.ps1`) | `%LOCALAPPDATA%\open-pdf` |

Builds before 2026-10-28 used `%LOCALAPPDATA%\Open PDF` and `Open PDF Data`.
A compiled build renames an old folder to the new name on first launch when the
new folder does not exist yet.

An installed build does not depend on its installation directory being
writable. A portable build writes nothing outside its own folder unless that
folder is read-only, so it normally leaves no trace on a machine it is run
from. Every storage directory is created on
first write, so a fresh portable folder needs no setup.

Verified from: platform/windows/open_pdf/config/path_handler.py [DATA_DIR];
platform/windows/open_pdf/config/path_handler.py [resolve_storage];
platform/windows/open_pdf/config/path_handler.py [resolve_exe_dir];
platform/windows/open_pdf/config/path_handler.py [resolve_user_data_dir];
platform/windows/open_pdf/gui/views/root_window/persistence.py
[PersistenceMixin]; platform/windows/open_pdf/adapters/persistence/desktop.py
[DesktopPersistence]; platform/windows/tests/test_path_handler.py
[test_storage_root_prefers_portable_over_local_app_data]

### Saved Runtime Settings

| Key | Type | Default | Description | Verified from |
| --- | --- | --- | --- | --- |
| `bookmarks_visible` | `bool` | `true` | Shows or hides the bookmarks pane on startup. | platform/windows/open_pdf/gui/models/window_state.py [PaneSettings] |
| `thumbnails_visible` | `bool` | `true` | Shows or hides the page thumbnails pane on startup. | platform/windows/open_pdf/gui/models/window_state.py [PaneSettings] |
| `text_visible` | `bool` | `true` | Shows or hides the extracted text pane on startup. | platform/windows/open_pdf/gui/models/window_state.py [PaneSettings] |
| `notes_visible` | `bool` | `true` | Shows or hides the editable document-notes pane on startup. | platform/windows/open_pdf/gui/models/window_state.py [PaneSettings] |
| `text_selection_mode` | `bool` | `true` | Legacy-compatible setting that keeps Read Mode text selection enabled. | platform/windows/open_pdf/gui/models/window_state.py [PaneSettings] |
| `thumbnails_on_left` | `bool` | `false` | Restores which side pane is placed on the left side of the window. | platform/windows/open_pdf/gui/models/window_state.py [PaneSettings] |
| `passwords` | `object` | `{}` | Stores remembered document-password entries keyed by normalized document path. | platform/windows/open_pdf/adapters/persistence/passwords.py [DocumentPasswordStore] |

### Environment Variable Notes

No user-settable environment variable is documented as part of normal usage. The
application does set `QT_QPA_FONTDIR` internally when bundled fonts are present,
and it reads `LOCALAPPDATA` to place per-user storage for packaged builds.

Verified from: platform/windows/open_pdf/main.py [_configure_qt_font_directory];
platform/windows/open_pdf/config/path_handler.py [resolve_user_data_dir]

## 9. Outputs, Exports, and Files

The `data/` and `logs/` paths below are relative to the build's storage root,
which section 8 lists per build shape.

| Path or Output | Purpose | When Created or Updated | Verified from |
| --- | --- | --- | --- |
| `data/ui-state.json` | Stores pane visibility, mouse mode, and side-pane placement. Installed builds place this under `%LOCALAPPDATA%\open-pdf`; portable builds place it beside the executable. | Updated when pane or layout settings change. | platform/windows/open_pdf/gui/views/root_window/window.py [_PANE_SETTINGS_PATH]; platform/windows/open_pdf/adapters/persistence/preferences.py [UiPreferencesStore] |
| `data/document-passwords.json` | Stores remembered PDF password entries as protected strings when platform support is available. Installed builds place this under `%LOCALAPPDATA%\open-pdf`; portable builds place it beside the executable. | Updated after a password is remembered, moved by a rename, or removed. | platform/windows/open_pdf/gui/views/root_window/window.py [_DOCUMENT_PASSWORDS_PATH]; platform/windows/open_pdf/adapters/persistence/passwords.py [DocumentPasswordStore]; platform/windows/open_pdf/adapters/persistence/protected_data.py [protect_string] |
| `data/ocr-cache/*.json` | Caches OCR text and word boxes per source document so results survive reopening. | Written after an OCR run, and read when a document is opened. | platform/windows/open_pdf/gui/views/root_window/window.py [_OCR_CACHE_DIRECTORY]; platform/windows/open_pdf/adapters/ocr/cache.py [OcrCache]; platform/windows/tests/test_app.py [test_open_document_loads_cached_ocr_results_without_backend] |
| `logs/Open_PDF.log` | Main rotating application log file. Installed builds place this under `%LOCALAPPDATA%\open-pdf`; portable builds place it beside the executable. | Created on app startup when logging is configured. | platform/windows/open_pdf/main.py [main]; platform/windows/open_pdf/config/logging/log_config.py [configure_logging] |
| `logs/Open_PDF.1.log`, `logs/Open_PDF.2.log`, `logs/Open_PDF.3.log` | Rotated backup logs beside the main log. | Created when the main log rolls over. | platform/windows/open_pdf/config/logging/log_config.py [_rotating_handler_factory] |
| `path/you/opened.pdf` | The current source PDF. | Updated by `Save`, including edits that require a full in-place rewrite instead of an incremental append. | platform/windows/open_pdf/application/document/session.py [save]; platform/windows/open_pdf/adapters/document/pymupdf/lifecycle.py [save_document_in_place] |
| `path/you/choose.pdf` | A saved copy of the active document, or the renamed document. | Created or replaced by `Save As` or `Rename File`. | platform/windows/open_pdf/application/document/session.py [save_as]; platform/windows/open_pdf/gui/views/root_window/window.py [_save_as]; platform/windows/open_pdf/application/document/rename.py [DocumentFileRenamer] |

## 10. Feature Reference

| Feature | What It Does | How to Access It | Verified from |
| --- | --- | --- | --- |
| Open from disk | Opens a PDF chosen from the file picker. | `File > Open` | platform/windows/open_pdf/gui/views/root_window/window.py [_choose_pdf] |
| Optional launch file | Opens a PDF passed on startup. | `open-pdf path/to/file.pdf` | platform/windows/open_pdf/main.py [build_argument_parser]; platform/windows/open_pdf/main.py [main] |
| Single running app instance | Reuses the existing app window and forwards later launch requests. | Launch the app again while it is already running. | platform/windows/open_pdf/adapters/runtime/single_instance.py [SingleInstanceCoordinator]; platform/windows/tests/test_main.py [test_single_instance_coordinator_forwards_pdf_path] |
| Multi-document tabs | Opens additional PDFs in separate tabs, reuses an existing tab for the same path, and keeps per-tab state across drag reordering. | Open another file while one is already loaded. | platform/windows/open_pdf/gui/views/root_window/tabs/document_tabs.py [_open_path_in_tab]; platform/windows/tests/test_app.py [test_opening_second_document_creates_new_tab_and_preserves_first_state]; platform/windows/tests/test_app.py [test_drag_reordering_tabs_preserves_session_state] |
| Single Page View | Shows only the current page in the main document view and uses `Up` / `Down` for page steps. | `View > Single Page View` | platform/windows/open_pdf/gui/views/root_window/window.py [_set_single_page_view_enabled]; platform/windows/open_pdf/gui/views/root_window/document_sync.py [_build_page_placeholders]; platform/windows/tests/test_app.py [test_single_page_view_shows_only_current_page] |
| Page thumbnails | Shows page previews for direct navigation. | `View > Thumbnails` and the thumbnails pane | platform/windows/open_pdf/gui/views/root_window/window.py [_build_side_panes]; platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py [ThumbnailNavigationMixin] |
| Bookmarks pane | Shows the PDF outline and app-created bookmarks. | `View > Bookmarks` and the bookmarks pane | platform/windows/open_pdf/gui/views/root_window/window.py [_build_side_panes]; platform/windows/tests/test_reader.py [test_outline_items_returns_pdf_bookmarks] |
| Document notes | Edits plain text stored as an embedded `notes.txt` attachment inside the PDF. | `View > Notes` and the notes pane | platform/windows/open_pdf/gui/views/root_window/window.py [_handle_notes_changed]; platform/windows/open_pdf/application/document/session.py [update_notes]; platform/windows/tests/test_app.py [test_notes_pane_edits_are_saved_inside_pdf] |
| Text search | Finds text and steps through matches as you type. | `Ctrl+F` and the search controls | platform/windows/open_pdf/gui/views/menus/toolbars.py [add_search_actions]; platform/windows/open_pdf/gui/views/search/search_navigation.py [_run_search]; platform/windows/tests/test_app.py [test_search_updates_as_user_types] |
| Text copy and selection overlay | Lets you select text from the extracted text pane or the page overlay and copy it. | Read Mode and context menus | platform/windows/open_pdf/gui/views/rendering/page_surface.py [createStandardContextMenu]; platform/windows/tests/test_app.py [test_page_text_overlay_uses_word_boxes_for_selection] |
| Bookmark creation from selected text | Creates a bookmark from selected text. | `Add Bookmark From Selection` in the text-selection context menu | platform/windows/open_pdf/gui/views/root_window/navigation/bookmarks.py [_add_bookmark_from_selected_text]; platform/windows/tests/test_app.py [test_page_overlay_context_menu_includes_selection_actions] |
| Remove content | Redacts the currently selected page region from the PDF. | `Edit PDF` on the tool bar, then `Remove Content` from the page-selection context menu or `Edit` menu | platform/windows/open_pdf/gui/views/menus/toolbars.py [add_pdf_edit_actions]; platform/windows/open_pdf/gui/views/menus/edit_menu.py [populate_edit_menu]; platform/windows/open_pdf/gui/views/workflows/text_editing.py [_remove_selected_text] |
| Replace text | Rewrites the single text span the current edit selection covers, shrinking an overlong replacement to stay on one line. | `Edit PDF` on the tool bar, then `Replace Text...` from the page-selection context menu | platform/windows/open_pdf/gui/views/workflows/text_editing.py [_replace_selected_text]; platform/windows/open_pdf/application/document/session.py [replace_text_span]; platform/windows/tests/test_text_editing.py [test_longer_replacement_shrinks_to_stay_on_one_line] |
| Insert blank page | Adds a blank page before or after the current page, matching the neighbouring page size. | `Edit > Insert Blank Page Before`, `Edit > Insert Blank Page After` | platform/windows/open_pdf/gui/views/menus/edit_menu.py [add_page_actions]; platform/windows/open_pdf/application/document/session.py [insert_blank_page]; platform/windows/tests/test_reader.py [test_inserted_page_matches_the_neighbour_page_size] |
| Page reordering | Moves the selected page one position earlier or later in the document. | The `Move page up` and `Move page down` buttons above the thumbnails list | platform/windows/open_pdf/gui/views/root_window/window.py [_move_current_page_by]; platform/windows/open_pdf/application/document/session.py [move_page]; platform/windows/tests/test_app.py [test_thumbnail_arrow_buttons_reorder_selected_page] |
| Bookmark rename and delete | Modifies or removes bookmarks from the bookmarks pane. | Bookmark context menu | platform/windows/open_pdf/gui/views/root_window/navigation/bookmarks.py [_rename_bookmark_item]; platform/windows/open_pdf/gui/views/root_window/navigation/bookmarks.py [_delete_bookmark_item] |
| Rotate page | Rotates a page clockwise. | Thumbnail context menu `Rotate Right` | platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py [_rotate_thumbnail_page]; platform/windows/tests/test_app.py [test_thumbnail_context_menu_can_rotate_its_page] |
| Page deletion | Removes a page from the document after confirmation. | Thumbnail context menu `Delete Page` | platform/windows/open_pdf/gui/views/root_window/panes/thumbnails.py [_delete_thumbnail_page]; platform/windows/tests/test_app.py [test_thumbnail_context_menu_can_delete_a_page] |
| OCR | Adds recognized text for a page or the whole document and caches the result per source file. | `Edit > Run OCR on Current Page`, `Edit > Run OCR on Document` | platform/windows/open_pdf/gui/views/menus/edit_menu.py [add_ocr_actions]; platform/windows/open_pdf/gui/ocr/workflow.py [OcrWorkflowMixin]; platform/windows/open_pdf/adapters/ocr/cache.py [OcrCache]; platform/windows/tests/test_app.py [test_ocr_page_action_updates_extracted_text_and_enables_actions] |
| Save and Save As | Writes the document back in place or to a chosen file. | `File > Save`, `File > Save As` | platform/windows/open_pdf/gui/views/root_window/window.py [_save]; platform/windows/open_pdf/gui/views/root_window/window.py [_save_as] |
| Rename file | Writes the document under a new name, removes the old file, and carries a remembered password across. | `File > Rename File` | platform/windows/open_pdf/gui/views/workflows/file_rename.py [_rename_file]; platform/windows/open_pdf/application/document/rename.py [DocumentFileRenamer]; platform/windows/tests/test_app.py [test_rename_file_replaces_old_path] |
| Print | Sends the current document to the system print dialog and printer. | `File > Print` | platform/windows/open_pdf/gui/views/workflows/printing.py [_print_document]; platform/windows/tests/test_app.py [test_print_document_honors_selected_page_range] |
| PDF properties editing | Edits Info Dictionary fields and raw XMP metadata. | `File > Properties` | platform/windows/open_pdf/gui/views/root_window/window.py [_edit_document_properties]; platform/windows/open_pdf/gui/views/dialogs/properties_dialog.py [DocumentPropertiesDialog] |
| Position-aware page history | Records the scroll position of each visited spot so returning restores where you were, not just the page. | Maintained automatically; no UI trigger in this version. | platform/windows/open_pdf/application/document/session.py [record_history_position]; platform/windows/open_pdf/domains/document/pages/history.py [ScrollState]; platform/windows/tests/test_page_history.py [test_go_back_restores_the_position_not_just_the_page] |
| Crash reporting | Routes unhandled exceptions to a crash dialog that names the log file. | Automatic on an unhandled error | platform/windows/open_pdf/config/crash_reporting.py [install_crash_handlers]; platform/windows/open_pdf/gui/views/dialogs/crash_dialog.py [QtCrashNotifier]; platform/windows/tests/test_crash_reporting.py |
| About dialog | Shows the application name and a one-line description. | `Help > About Open PDF` | platform/windows/open_pdf/gui/views/menus/help/about_open_pdf.py [show_about_open_pdf_dialog]; platform/windows/tests/test_app.py [test_file_menu_has_exit_and_help_menu_has_about] |
| Layout persistence | Remembers pane visibility, text-selection mode, and which side pane is on the left. | Automatic between launches | platform/windows/open_pdf/gui/views/root_window/persistence.py [_persist_pane_visibility_settings]; platform/windows/tests/test_app.py [test_pane_visibility_persists_between_windows] |

## 11. Troubleshooting

| Symptom | Likely Cause | Resolution | Verified from |
| --- | --- | --- | --- |
| A PDF does not open and you are prompted for a password. | The PDF is encrypted. | Enter the correct password. If the first password is wrong, Open PDF prompts again. If you cancel the prompt, the file is not opened. | platform/windows/open_pdf/gui/views/root_window/window.py [_open_document]; platform/windows/open_pdf/gui/views/root_window/window.py [_prompt_for_document_password]; platform/windows/tests/test_app.py [test_open_document_prompts_for_password_and_retries_until_success]; platform/windows/tests/test_app.py [test_open_document_returns_when_password_prompt_is_cancelled] |
| A remembered password stops working. | The stored password entry is invalid or outdated. | Re-enter the password when prompted. The app forgets invalid remembered passwords and stores the new one after a successful open. | platform/windows/open_pdf/gui/views/root_window/persistence.py [_recall_document_password]; platform/windows/open_pdf/gui/views/root_window/persistence.py [_forget_document_password]; platform/windows/tests/test_app.py [test_invalid_remembered_password_is_forgotten_and_replaced] |
| The OCR actions are greyed out. | The document has unsaved changes, an OCR run is already in progress, or no Tesseract backend was found. | Save the document, wait for the running OCR job, or install Tesseract. Open PDF shows setup guidance when the backend is missing. | platform/windows/open_pdf/gui/views/root_window/window.py [_refresh_actions]; platform/windows/open_pdf/main.py [_default_ocr_unavailable_message]; platform/windows/tests/test_app.py [test_ocr_action_shows_tesseract_setup_guidance_when_backend_missing] |
| `Replace Text...` reports that no editable text was found. | The edit selection does not cover a single editable text span, for example because the page region is an image. | Reselect a tighter rectangle over real text, or use `Remove Content` instead. | platform/windows/open_pdf/gui/views/workflows/text_editing.py [_replace_selected_text]; platform/windows/open_pdf/application/document/session.py [span_for_rectangles] |
| The `Move page up` or `Move page down` button is greyed out. | The selected page is already the first or the last page of the document. | Select a different page in the thumbnails pane. | platform/windows/open_pdf/gui/views/root_window/window.py [_refresh_actions] |
| `Save` is disabled or cannot complete. | Either there are no unsaved changes, or the source file cannot be rewritten successfully. | Retry `File > Save`. If the save still fails, use `File > Save As` to write a copy to a new file. | platform/windows/open_pdf/application/document/session.py [can_save]; platform/windows/open_pdf/application/document/session.py [save]; platform/windows/open_pdf/adapters/document/pymupdf/lifecycle.py [save_document_in_place]; platform/windows/open_pdf/gui/views/root_window/window.py [_save_as] |
| `Rename File` reports that cleanup was incomplete. | The document was written under its new name, but the old file could not be removed. | Delete the leftover source file manually. The renamed document stays open and valid. | platform/windows/open_pdf/gui/views/workflows/file_rename.py [_perform_file_rename]; platform/windows/open_pdf/application/document/rename.py [DocumentFileRenamer] |
| Closing the tab or window appears to do nothing. | A close was cancelled because unsaved changes were not resolved. | In the `Unsaved Changes` prompt, choose `Save`, `Discard`, or `Cancel`. `Cancel` keeps the document open. | platform/windows/open_pdf/gui/views/root_window/window.py [_confirm_unsaved_changes]; platform/windows/open_pdf/gui/views/root_window/window.py [closeEvent]; platform/windows/tests/test_app.py [test_close_event_cancel_keeps_unsaved_document_open] |
| Printing sends the wrong pages. | The print dialog honors the selected print range. | Reopen `File > Print` and confirm whether the dialog is set to all pages, the current page, or a page range. | platform/windows/open_pdf/gui/views/workflows/printing.py [_selected_print_page_indexes]; platform/windows/tests/test_app.py [test_print_document_honors_selected_page_range] |
| Search shows no results. | The query is not present in the current in-memory document state. | Refine the query or confirm that the text still exists after edits such as page deletion. Open PDF searches the current in-memory document, not an old on-disk copy. | platform/windows/open_pdf/gui/views/root_window/window.py [_update_search_bar_state]; platform/windows/tests/test_app.py [test_dirty_document_search_uses_in_memory_state] |

## 12. FAQ

**Can I open a PDF directly from the command line?**

Yes. Use `open-pdf path/to/file.pdf`.

Verified from: platform/windows/pyproject.toml [project.scripts];
platform/windows/open_pdf/main.py [build_argument_parser]

**Can I run more than one main window at the same time?**

Open PDF is designed around a single primary UI process. Later launches activate
the existing window and can forward another PDF to that running instance.

Verified from: platform/windows/open_pdf/adapters/runtime/single_instance.py
[SingleInstanceCoordinator]; platform/windows/tests/test_main.py
[test_single_instance_coordinator_forwards_pdf_path]

**Does Open PDF remember my layout choices?**

Yes. Pane visibility, text-selection mode, and side-pane placement are persisted
between launches in `data/ui-state.json`.

Verified from: platform/windows/open_pdf/gui/views/root_window/persistence.py
[_persist_pane_visibility_settings]; platform/windows/tests/test_app.py
[test_pane_visibility_persists_between_windows];
platform/windows/tests/test_app.py [test_mouse_mode_persists_between_windows]

**Does Open PDF remember PDF passwords?**

On Windows, yes. Remembered passwords are stored as protected values in
`data/document-passwords.json`. If the platform protection helper is
unavailable, remembered passwords are not available.

Verified from: platform/windows/open_pdf/adapters/persistence/protected_data.py
[protect_string]; platform/windows/open_pdf/gui/views/root_window/persistence.py
[_remember_document_password];
platform/windows/open_pdf/adapters/persistence/passwords.py
[DocumentPasswordStore]

**Can I save over the original PDF?**

Yes, when there are unsaved changes and the PDF was opened from disk. Open PDF
saves in place when possible and falls back to a full in-place rewrite when
incremental save is unavailable.

Verified from: platform/windows/open_pdf/application/document/session.py
[can_save]; platform/windows/open_pdf/application/document/session.py [save];
platform/windows/open_pdf/adapters/document/pymupdf/lifecycle.py
[save_document_in_place]

**What is the difference between `Save As` and `Rename File`?**

`Save As` writes a copy and leaves the original file in place. `Rename File`
writes the document under the new name and then removes the original, moving any
remembered password with it.

Verified from: platform/windows/open_pdf/gui/views/root_window/window.py
[_save_as]; platform/windows/open_pdf/gui/views/workflows/file_rename.py
[_perform_file_rename]; platform/windows/tests/test_app.py
[test_rename_file_replaces_old_path]

**Do OCR results survive closing the document?**

Yes. Results are cached per source file under `data/ocr-cache/` and reloaded
when the document is opened again, even without an OCR backend installed.

Verified from: platform/windows/open_pdf/adapters/ocr/cache.py [OcrCache];
platform/windows/tests/test_app.py
[test_open_document_loads_cached_ocr_results_without_backend]

## 13. Glossary

| Term | Definition | Verified from |
| --- | --- | --- |
| Menu bar | The top application menu strip, holding the `File`, `Edit`, `View`, and `Help` menus. | README.md; platform/windows/open_pdf/gui/views/menus/file_menu_bar.py [build_menu_bar] |
| Tool bar | The strip below the menu bar with the page selector, `Edit PDF`, `Fit Page`, the search bar, and the mouse-mode indicator. | README.md; platform/windows/open_pdf/gui/views/menus/toolbars.py [build_toolbar] |
| Page thumbnails | The pane that lists page previews for direct navigation, with the page move buttons above it. | README.md; platform/windows/open_pdf/gui/views/root_window/window.py [_build_side_panes] |
| Document view | The central scrolling PDF surface. | README.md; platform/windows/open_pdf/gui/views/root_window/window.py [_build_document_view] |
| Bookmarks | The pane that shows the PDF outline tree and user-created bookmarks. | README.md; platform/windows/open_pdf/gui/views/root_window/window.py [_build_side_panes] |
| Status bar | The strip along the bottom of the main window that shows page, zoom, search, and OCR progress. | README.md; platform/windows/open_pdf/gui/views/root_window/window.py [_update_status_bar] |
| Edit PDF mode | The interaction mode that lets you drag out a page rectangle for content removal or text replacement. | platform/windows/open_pdf/gui/views/rendering/selection.py [_enter_pdf_edit_mode]; platform/windows/open_pdf/gui/views/rendering/page_surface.py [set_edit_selection_enabled] |
| Read Mode | The normal document interaction mode, including text selection in the extracted text pane and page overlay. | platform/windows/open_pdf/gui/views/menus/view_menu.py [add_mouse_mode_actions]; platform/windows/tests/test_app.py [test_text_selection_mode_updates_toolbar_indicator_and_page_overlay] |
| Text span | One run of same-styled text on a page. `Replace Text...` rewrites exactly one span at a time. | platform/windows/open_pdf/domains/document/pages/text/spans.py; platform/windows/open_pdf/application/document/session.py [text_spans] |
| Page history | The back and forward navigation stack, where each entry records a page and the scroll position within it. | platform/windows/open_pdf/domains/document/pages/history.py [PageHistory]; platform/windows/open_pdf/domains/document/pages/history.py [ScrollState] |
