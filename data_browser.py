"""Window with a sortable, filterable table of the current data set."""
import tkinter as tk
from tkinter import simpledialog, ttk

STATUS_FILTERS = {
    "all": "Wszystkie",
    "nondominated": "Niezdominowane",
    "dominated": "Zdominowane",
    "compared": "Porównywane",
}


class DataBrowser(tk.Toplevel):
    def __init__(self, master, on_select, on_rename, on_close):
        """
        on_select(ids)            – called with the list of selected point ids
        on_rename(index, name)    – called when the user renames criterion `index`
        on_close()                – called when the window is closed
        """
        super().__init__(master)
        self.title("Przeglądanie danych")
        self.geometry("720x560")
        self.on_select = on_select
        self.on_rename = on_rename
        self.on_close = on_close

        self.rows = []            # (id, *values, status, n_compared) for every point
        self.has_result = False
        self.n_criteria = 0
        self.sort_column = 0
        self.sort_descending = False

        top = ttk.Frame(self, padding=6)
        top.pack(fill="x")
        ttk.Label(top, text="Pokaż").pack(side="left")
        self.filter_var = tk.StringVar(value=STATUS_FILTERS["all"])
        self.filter_combo = ttk.Combobox(top, textvariable=self.filter_var, values=list(STATUS_FILTERS.values()),
                                         state="readonly", width=16)
        self.filter_combo.pack(side="left", padx=4)
        self.filter_combo.bind("<<ComboboxSelected>>", lambda _: self._fill_table())
        ttk.Button(top, text="Odznacz", command=self._clear_selection).pack(side="left", padx=4)
        self.count_var = tk.StringVar()
        ttk.Label(top, textvariable=self.count_var).pack(side="right")

        ttk.Label(self, text="Klik w nagłówek – sortowanie, prawy klik w nagłówek kryterium – zmiana nazwy. "
                             "Zaznaczone wiersze są wyróżnione na wykresie.",
                  foreground="gray", padding=(6, 0)).pack(fill="x")

        frame = ttk.Frame(self, padding=6)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, show="headings", selectmode="extended")
        y_scroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.tag_configure("nondominated", background="#dff3df")

        self.tree.bind("<<TreeviewSelect>>", self._selection_changed)
        # Right click is <Button-2> on macOS and <Button-3> elsewhere; Ctrl+click as a fallback
        for sequence in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.tree.bind(sequence, self._heading_right_click)
        self.protocol("WM_DELETE_WINDOW", self._close)

    # ------------------------------------------------------------ data
    def set_data(self, points, nondominated_mask, compared_counts, names):
        self.n_criteria = len(points[0]) if points else len(names)
        self.has_result = nondominated_mask is not None
        self.rows = []
        for i, point in enumerate(points):
            if self.has_result:
                status = "niezdominowany" if nondominated_mask[i] else "zdominowany"
                n_compared = int(compared_counts[i])
            else:
                status, n_compared = "–", 0
            self.rows.append((i, *point, status, n_compared))
        self.filter_combo.state(["!disabled"] if self.has_result else ["disabled"])
        if not self.has_result:
            self.filter_var.set(STATUS_FILTERS["all"])
        self._build_columns(names)
        self._fill_table(keep_selection=False)

    def set_names(self, names):
        """Rename the criterion columns without reloading the rows."""
        for i in range(self.n_criteria):
            self.tree.heading(f"c{i}", text=names[i] if i < len(names) else f"f{i + 1}")
        self._update_sort_arrow()

    def _build_columns(self, names):
        columns = ["id"] + [f"c{i}" for i in range(self.n_criteria)] + ["status", "compared"]
        self.tree.configure(columns=columns)
        self.tree.column("id", width=60, anchor="e", stretch=False)
        for i in range(self.n_criteria):
            self.tree.column(f"c{i}", width=100, anchor="e")
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("compared", width=150, anchor="e")
        for position, column in enumerate(columns):
            self.tree.heading(column, command=lambda p=position: self._sort_by(p))
        if self.sort_column >= len(columns):
            self.sort_column, self.sort_descending = 0, False
        self.tree.heading("id", text="id")
        self.tree.heading("status", text="status")
        self.tree.heading("compared", text="udział w porównaniach")
        self.set_names(names)

    def _visible_rows(self):
        status_filter = next(k for k, v in STATUS_FILTERS.items() if v == self.filter_var.get())
        status_column = 1 + self.n_criteria
        if status_filter == "nondominated":
            rows = [r for r in self.rows if r[status_column] == "niezdominowany"]
        elif status_filter == "dominated":
            rows = [r for r in self.rows if r[status_column] == "zdominowany"]
        elif status_filter == "compared":
            rows = [r for r in self.rows if r[-1] > 0]
        else:
            rows = self.rows
        return sorted(rows, key=lambda r: r[self.sort_column], reverse=self.sort_descending)

    def _fill_table(self, keep_selection=True):
        selected = set(self.tree.selection()) if keep_selection else set()
        self.tree.delete(*self.tree.get_children())
        rows = self._visible_rows()
        for row in rows:
            values = (row[0], *(f"{v:.6g}" for v in row[1:1 + self.n_criteria]), *row[1 + self.n_criteria:])
            tags = ("nondominated",) if row[1 + self.n_criteria] == "niezdominowany" else ()
            self.tree.insert("", "end", iid=str(row[0]), values=values, tags=tags)
        still_visible = [iid for iid in selected if self.tree.exists(iid)]
        self.tree.selection_set(still_visible)
        self.count_var.set(f"Wierszy: {len(rows)} / {len(self.rows)}")
        self._update_sort_arrow()

    # ------------------------------------------------------- interaction
    def _sort_by(self, position):
        if self.sort_column == position:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_column, self.sort_descending = position, False
        self._fill_table()

    def _update_sort_arrow(self):
        arrow = " ▼" if self.sort_descending else " ▲"
        for position, column in enumerate(self.tree["columns"]):
            text = self.tree.heading(column, "text").rstrip(" ▲▼")
            self.tree.heading(column, text=text + (arrow if position == self.sort_column else ""))

    def _heading_right_click(self, event):
        if self.tree.identify_region(event.x, event.y) != "heading":
            return None
        column = self.tree.column(self.tree.identify_column(event.x), "id")
        if not column.startswith("c"):
            return "break"
        index = int(column[1:])
        current = self.tree.heading(column, "text").rstrip(" ▲▼")
        name = simpledialog.askstring("Nazwa kryterium", f"Nowa nazwa kryterium {index + 1}:",
                                      initialvalue=current, parent=self)
        if name is not None:
            self.on_rename(index, name)
        return "break"

    def _selection_changed(self, _event=None):
        self.on_select([int(iid) for iid in self.tree.selection()])

    def _clear_selection(self):
        self.tree.selection_set([])

    def _close(self):
        self.on_close()
        self.destroy()
