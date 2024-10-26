import base64
import json
import os
import uuid
from datetime import datetime
from functools import reduce
from xml.sax.saxutils import escape

from PIL import ImageFont, Image, ImageDraw
from anytree import PreOrderIter, NodeMixin
from anytree.exporter import JsonExporter, DictExporter
from actions import BaseTelegramAction
from xml_constants import *


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BaseTelegramAction):
            return repr(obj)
        return super().default(obj)


class Table(NodeMixin):
    """drawio table"""

    def __init__(self, origin, parent=None):
        self.id = origin.state_id
        self.origin = origin
        self.table_x = None
        self.table_y = None
        self.table_width = BASE_TABLE_WIDTH
        self.table_height = None
        self.rows = []
        self.parent = parent
        self.edge = None if parent is None else Edge(parent.id, self.id)
        self.__prerender()

    def __prerender(self):
        counter = 0
        order = ["state_id", "action_in", "status", "media", "text", "actions_out"]
        sorted_items = sorted(
            self.origin.__dict__.items(),
            key=lambda item: order.index(item[0]) if item[0] in order else len(order),
        )

        for key, value in sorted_items:
            if key not in ("_NodeMixin__children", "_NodeMixin__parent"):
                self.rows.append(Row(key, value, table=self, index=counter))
                counter += 1

        self.table_height = reduce(
            lambda height, row: height + row.row_height, self.rows, 0
        )

    def __eq__(self, other):
        if not isinstance(self, type(other)):
            return False
        else:
            return self.rows == other.rows


class Row:
    """drawio row"""

    def __init__(self, key, value, table, index):
        self.id = f"{table.id}-{index + 1}"
        self.cells = [Cell(self, key, 0), Cell(self, value, 1)]
        self.row_y = 0
        self.row_width = BASE_TABLE_WIDTH
        self.row_height = max([cell.cell_height for cell in self.cells])
        self.parent = table
        self.__prerender()

    def __prerender(self):
        self.cells[0].cell_height = self.cells[1].cell_height

    def __eq__(self, other):
        return self.cells == other.cells


class Cell:
    """drawio cell"""

    def __init__(self, row, value, index):
        self.id = f"{row.id}-{index + 1}"
        self.value = value
        self.cell_x = 0 if index == 0 else BASE_TABLE_WIDTH * BASE_CELL_SHARE
        self.cell_width = BASE_TABLE_WIDTH * (
            BASE_CELL_SHARE if index == 0 else 1 - BASE_CELL_SHARE
        )
        self.cell_height = None
        self.parent = row
        self.__prerender()

    def __prerender(self):
        if isinstance(self.value, str) and os.path.exists(self.value):
            file_extension = os.path.splitext(self.value)[1].lower()
            if file_extension in [".jpg", ".jpeg", ".png", ".gif"]:
                encoded_image, width, height = self.image_to_base64(self.value)
                self.value = f'<div><img height="{height}" width="{width}" src="data:image/jpeg;base64,{encoded_image}"><br></div>'
                self.cell_height = height
            elif file_extension in [".mp4", ".avi", ".mov"]:
                self.value = f'<div><video controls><source src="{self.value}" type="video/{file_extension[1:]}"></video><br></div>'
                self.cell_height = 200
            else:
                self.value = f'<div><a href="{self.value}" target="_blank">Open File</a><br></div>'
        elif isinstance(self.value, list):
            self.value = "\n".join(map(str, self.value))
        elif isinstance(self.value, str):
            if len(self.value) > MAX_STR_LEN:
                # to bypass errors connected with pyrogram iternal proccesses
                success = 0
                slice_len = MAX_STR_LEN
                while success == 0:
                    try:
                        self.value = self.value[:slice_len] + "..."
                        success = 1
                    except Exception:
                        slice_len -= 1

        else:
            self.value = str(self.value)

        if self.cell_height is None:
            self.cell_height = self.calculate_cell_height(self.value)

        self.value = escape(
            self.value,
            {  # xml.sax.saxutils.escape
                '"': "&quot;",
                "'": "&apos;",
                "\n": "&lt;br&gt;",
            },
        )

    def image_to_base64(self, image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        image = Image.open(image_path)
        original_width, original_height = image.size
        aspect_ratio = original_height / original_width

        if original_width > self.cell_width:
            width = self.cell_width
            height = width * aspect_ratio
        else:
            width = original_width
            height = original_height

        return encoded_string, int(width), int(height)

    def calculate_cell_height(
        self,
        text,
        font_path=FONT_PATH,
        font_size=FONT_SIZE,
        max_width=BASE_TABLE_WIDTH * (1 - BASE_CELL_SHARE),
    ):

        font_path = os.path.abspath(font_path)
        font = ImageFont.truetype(font_path, font_size)

        dummy_image = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_image)

        lines = []
        for line in text.split("\n"):
            words = line.split(" ")
            current_line = ""
            for word in words:
                test_line = f"{current_line} {word}".strip()
                bbox = draw.textbbox((0, 0), test_line, font=font)
                line_width = bbox[2] - bbox[0]
                if line_width <= max_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            lines.append(current_line)

        ascent, descent = font.getmetrics()
        line_height = ascent + descent

        # just some free aditional space for nice view
        additional_space = 50 if len(lines) > 1 else 10
        total_height = line_height * len(lines) + additional_space

        return total_height

    def __eq__(self, other):
        return self.value == other.value


class Edge:
    """drawio edge to connect tables"""

    def __init__(self, source_id, target_id):
        self.id = str(uuid.uuid4())
        self.source = f"{source_id}-3"
        self.target = f"{target_id}-3"


class Exporter:
    def __init__(self, tester):
        self.tester = tester
        self.render_root = None
        self.render_pool = []
        self.tree_width_by_levels = None
        self.mapping_state_tree_to_render_tree = {}

    def _custom_attr_iter(self, node):
        """custom function to process attrs of nodes for nice view"""
        res = []
        actions_out_item = None

        for k, v in node:
            v = str(v).strip("[]")
            if k == "actions_out":
                actions_out_item = (k, v)
            else:
                res.append((k, v))

        if actions_out_item:
            res.append(actions_out_item)
        return res

    def get_element_from_list_safely(self, lst, index, default=None):
        try:
            return lst[index]
        except IndexError:
            return default

    def _initialize_render_tree(self):
        for node in PreOrderIter(self.tester.root):
            if node.depth == 0:
                self.render_root = Table(origin=self.tester.root)
                self.render_pool.append(self.render_root)
                self.mapping_state_tree_to_render_tree[node] = self.render_root
            else:
                render_node = Table(
                    origin=node,
                    parent=self.mapping_state_tree_to_render_tree[node.parent],
                )
                self.render_pool.append(render_node)
                self.mapping_state_tree_to_render_tree[node] = render_node

    def _initialize_render_matrix(self):
        self.render_paths = []
        for leaf in PreOrderIter(self.tester.root, filter_=lambda n: n.is_leaf):
            path = []
            previous_table = None
            for node in leaf.path:
                table = Table(origin=node)
                if previous_table is not None:
                    edge = Edge(previous_table.id, table.id)
                    table.edge = edge
                path.append(table)
                previous_table = table
            self.render_paths.append(path)

    def _layout_render_tree(self, node, y_position):
        # set table_x
        node.table_x = (
            BASE_START_TABLE_X_AXIS
            + node.depth * BASE_TABLE_WIDTH
            + node.depth * MARGIN
        )

        # layout rows within table
        current_row_y = 0
        for row in node.rows:
            row.row_y = current_row_y
            current_row_y += row.row_height

        if not node.children:
            node.table_y = y_position
            return y_position + node.table_height + MARGIN

        child_y_position = y_position

        for child in node.children:
            child_y_position = self._layout_render_tree(child, child_y_position)

        min_child_y = node.children[0].table_y
        max_child_y = node.children[-1].table_y + node.children[-1].table_height
        node.table_y = (min_child_y + max_child_y) / 2 - node.table_height / 2

        return max(child_y_position, node.table_y + node.table_height + MARGIN)

    def _layout_render_matrix(self, y_position):
        current_y_position = y_position
        for path in self.render_paths:
            max_table_height = 0
            for table in path:
                table.table_x = (
                        BASE_START_TABLE_X_AXIS
                        + table.origin.depth * (BASE_TABLE_WIDTH + MARGIN)
                )
                table.table_y = current_y_position
                current_row_y = 0
                for row in table.rows:
                    row.row_y = current_row_y
                    current_row_y += row.row_height
                if table.table_height > max_table_height:
                    max_table_height = table.table_height
            current_y_position += max_table_height + MARGIN

    def _fill_xml_with_tree(self, table):
        main_str = ""
        # add shape=table to xml
        main_str += BASE_TABLE.format(
            table.id,
            table.table_x,
            table.table_y,
            table.table_width,
            table.table_height,
        )

        # add shape=tableRow and shape=partialRectangle to xml
        for row in table.rows:
            main_str += BASE_ROW.format(
                row.id, row.parent.id, row.row_y, row.row_width, row.row_height
            )

            main_str += BASE_CELL.format(
                row.cells[0].id,
                row.cells[0].value,
                row.cells[0].parent.id,
                row.cells[0].cell_x,
                row.cells[0].cell_width,
                row.cells[0].cell_height,
            )

            main_str += BASE_CELL.format(
                row.cells[1].id,
                row.cells[1].value,
                row.cells[1].parent.id,
                row.cells[1].cell_x,
                row.cells[1].cell_width,
                row.cells[1].cell_height,
            )

        if table.children:
            for index, child in enumerate(table.children):
                main_str += self._fill_xml_with_tree(child)

        if table.parent:
            main_str += BASE_EDGE.format(str(uuid.uuid4()), table.parent.id, table.id)
        return main_str

    def _fill_xml_with_matrix(self):
        main_str = ""
        for i, path in enumerate(self.render_paths):
            for n, table in enumerate(path):
                if i == 0 or (i != 0 and table != self.get_element_from_list_safely(self.render_paths[i-1], n)):
                    # Add table to XML
                    main_str += BASE_TABLE.format(
                        f'{table.id}_{i}',
                        table.table_x,
                        table.table_y,
                        table.table_width,
                        table.table_height,
                    )
                    # Add rows and cells
                    for row in table.rows:
                        main_str += BASE_ROW.format(
                            f'{row.id}_{i}', f'{table.id}_{i}', row.row_y, row.row_width, row.row_height
                        )
                        for cell in row.cells:
                            main_str += BASE_CELL.format(
                                f'{cell.id}_{i}',
                                cell.value,
                                f'{row.id}_{i}',
                                cell.cell_x,
                                cell.cell_width,
                                cell.cell_height,
                            )
                # # Add edge if it exists
                # if table.edge:
                #     main_str += BASE_EDGE.format(f'{table.edge.id}_{i}', f'{table.edge.source}_{i}', f'{table.edge.target}_{i}')

        export_string = BASE_PAGE.format(main_str)
        export_string = export_string.strip("\n")
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"tree_{formatted_time}.xml"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(export_string)
        return

    def export_to_json(self, save=False):
        exporter = JsonExporter(
            indent=2,
            ensure_ascii=False,
            cls=CustomEncoder,
            dictexporter=DictExporter(attriter=self._custom_attr_iter),
        )

        tree = exporter.export(self.tester.root)

        if save:
            current_time = datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"tree_{formatted_time}.json"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(tree)

        return tree

    def export_to_drawio(self, mode='tree'):
        if mode == 'tree':
            self._initialize_render_tree()
            self._layout_render_tree(self.render_root, BASE_START_TABLE_Y_AXIS)
            self._fill_xml_with_tree(self.render_root)
        elif mode == 'matrix':
            self._initialize_render_matrix()
            self._layout_render_matrix(BASE_START_TABLE_Y_AXIS)
            self._fill_xml_with_matrix()
        else:
            raise ValueError('Unknown mode')
