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
        order = ['state_id', 'action_in', 'status', 'media', 'text', 'actions_out']
        sorted_items = sorted(self.origin.__dict__.items(),
                              key=lambda item: order.index(item[0]) if item[0] in order else len(order))

        for key, value in sorted_items:
            if key not in ('_NodeMixin__children', '_NodeMixin__parent'):
                self.rows.append(Row(key, value, table=self, index=counter))
                counter += 1

        self.table_height = reduce(
            lambda height, row: height + row.row_height,
            self.rows,
            0
        )


class Row:
    """drawio row"""

    def __init__(self, key, value, table, index):
        self.id = f'{table.id}-{index + 1}'
        self.cells = [Cell(self, key, 0), Cell(self, value, 1)]
        self.row_y = 0
        self.row_width = BASE_TABLE_WIDTH
        self.row_height = max([cell.cell_height for cell in self.cells])
        self.parent = table
        self.__prerender()

    def __prerender(self):
        self.cells[0].cell_height = self.cells[1].cell_height


class Cell:
    """drawio cell"""

    def __init__(self, row, value, index):
        self.id = f'{row.id}-{index + 1}'
        self.value = value
        self.cell_x = 0 if index == 0 else BASE_TABLE_WIDTH*BASE_CELL_SHARE
        self.cell_width = BASE_TABLE_WIDTH*(BASE_CELL_SHARE if index == 0 else 1-BASE_CELL_SHARE)
        self.cell_height = None
        self.parent = row
        self.__prerender()

    def __prerender(self):
        if isinstance(self.value, str) and os.path.exists(self.value):
            encoded_image = self.image_to_base64(self.value)
            self.value = f'<div><img height="256" width="256" src="data:image/jpeg;base64,{encoded_image}"><br></div>'
        elif isinstance(self.value, list):
            self.value = "\n".join(map(str, self.value))
        elif isinstance(self.value, str):
            if len(self.value) > MAX_STR_LEN:
                # to bypass errors connected with pyrogram iternal proccesses
                success = 0
                slice_len = MAX_STR_LEN
                while success == 0:
                    try:
                        self.value = self.value[:slice_len] + '...'
                        success = 1
                    except Exception:
                        slice_len -= 1

        else:
            self.value = str(self.value)

        self.cell_height = self.calculate_cell_height(self.value)

        self.value = escape(self.value, {  # xml.sax.saxutils.escape
            '"': '&quot;',
            "'": '&apos;',
            '\n': '&lt;br&gt;'
        })

    def image_to_base64(self, image_path):
        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
        return encoded_string

    def calculate_cell_height(self,
                              text,
                              font_path=FONT_PATH,
                              font_size=FONT_SIZE,
                              max_width=BASE_TABLE_WIDTH*(1-BASE_CELL_SHARE)):

        font_path = os.path.abspath(font_path)
        font = ImageFont.truetype(font_path, font_size)

        dummy_image = Image.new('RGB', (1, 1))
        draw = ImageDraw.Draw(dummy_image)

        lines = []
        for line in text.split('\n'):
            words = line.split(' ')
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
            v = str(v).strip('[]')
            if k == "actions_out":
                actions_out_item = (k, v)
            else:
                res.append((k, v))

        if actions_out_item:
            res.append(actions_out_item)
        return res

    def export_to_json(self, save=False):
        exporter = JsonExporter(indent=2,
                                ensure_ascii=False,
                                cls=CustomEncoder,
                                dictexporter=DictExporter(
                                    attriter=self._custom_attr_iter
                                )
                                )

        tree = exporter.export(self.tester.root)

        if save:
            current_time = datetime.now()
            formatted_time = current_time.strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"tree_{formatted_time}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(tree)

        return tree

    def create_render_tree(self):
        for node in PreOrderIter(self.tester.root):
            if node.depth == 0:
                self.render_root = Table(origin=self.tester.root)
                self.render_pool.append(self.render_root)
                self.mapping_state_tree_to_render_tree[node] = self.render_root
            else:
                render_node = Table(origin=node, parent=self.mapping_state_tree_to_render_tree[node.parent])
                self.render_pool.append(render_node)
                self.mapping_state_tree_to_render_tree[node] = render_node

    def layout_render_tree(self, node, y_position):
        # set table_x
        node.table_x = BASE_START_TABLE_X_AXIS + node.depth*BASE_TABLE_WIDTH + node.depth*MARGIN

        # layout rows within table
        current_row_y = 0
        for i, row in enumerate(node.rows):
            row.row_y = current_row_y
            current_row_y += row.row_height

        if not node.children:
            node.table_y = y_position
            return y_position + node.table_height + MARGIN

        child_y_position = y_position

        for child in node.children:
            child_y_position = self.layout_render_tree(child, child_y_position)

        min_child_y = node.children[0].table_y
        max_child_y = node.children[-1].table_y + node.children[-1].table_height
        node.table_y = (min_child_y + max_child_y) / 2 - node.table_height / 2

        return max(child_y_position, node.table_y + node.table_height + MARGIN)

    def write_to_xml(self):
        main_str = self.recursive_fill_xml(self.render_root)
        export_string = BASE_PAGE.format(main_str)
        export_string = export_string.strip("\n")
        current_time = datetime.now()
        formatted_time = current_time.strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"tree_{formatted_time}.xml"
        with open(filename, "w", encoding='utf-8') as f:
            f.write(export_string)
        return

    def recursive_fill_xml(self, table):
        main_str = ""
        # add shape=table to xml
        main_str += BASE_TABLE.format(table.id,
                                      table.table_x,
                                      table.table_y,
                                      table.table_width,
                                      table.table_height
                                      )

        # add shape=tableRow and shape=partialRectangle to xml
        for row in table.rows:
            main_str += BASE_ROW.format(row.id,
                                        row.parent.id,
                                        row.row_y,
                                        row.row_width,
                                        row.row_height
                                        )

            main_str += BASE_CELL.format(row.cells[0].id,
                                         row.cells[0].value,
                                         row.cells[0].parent.id,
                                         row.cells[0].cell_x,
                                         row.cells[0].cell_width,
                                         row.cells[0].cell_height
                                         )

            main_str += BASE_CELL.format(row.cells[1].id,
                                         row.cells[1].value,
                                         row.cells[1].parent.id,
                                         row.cells[1].cell_x,
                                         row.cells[1].cell_width,
                                         row.cells[1].cell_height
                                         )

        if table.children:
            for index, child in enumerate(table.children):
                main_str += self.recursive_fill_xml(child)

        if table.parent:
            main_str += BASE_EDGE.format(str(uuid.uuid4()),
                                         table.parent.id,
                                         table.id)
        return main_str

    def export_to_drawio(self):
        self.create_render_tree()
        self.layout_render_tree(self.render_root, BASE_START_TABLE_Y_AXIS)
        self.write_to_xml()
