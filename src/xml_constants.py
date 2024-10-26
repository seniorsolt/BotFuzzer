BASE_START_TABLE_X_AXIS = 160
BASE_START_TABLE_Y_AXIS = 104
BASE_TABLE_WIDTH = 1000
MARGIN = 100
BASE_CELL_SHARE = 0.2
MAX_STR_LEN = 1000
FONT_PATH = 'src/Helvetica.ttf'
FONT_SIZE = 30

BASE_PAGE = """
<mxfile host="65bd71144e">
    <diagram id="P0SbFD_KFt-Lh6b_J3Es" name="Page-1">
        <mxGraphModel dx="642" dy="83" grid="0" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="0" pageScale="1" pageWidth="850" pageHeight="1100" math="0" shadow="0">
            <root>
                <mxCell id="y"/>
                <mxCell id="x" parent="y"/>
                {}
            </root>
        </mxGraphModel>
    </diagram>
</mxfile>
"""

BASE_TABLE = f"""
\t\t\t\t<mxCell id="{{}}" value="" style="shape=table;startSize=0;container=1;collapsible=0;childLayout=tableLayout;fontSize={FONT_SIZE};spacing=0;spacingLeft=5;spacingTop=1" parent="x" vertex="1">
\t\t\t\t  <mxGeometry x="{{}}" y="{{}}" width="{{}}" height="{{}}" as="geometry" />
\t\t\t\t</mxCell>
"""


BASE_ROW = f"""
\t\t\t\t<mxCell id="{{}}" value="" style="shape=tableRow;horizontal=0;startSize=0;swimlaneHead=0;swimlaneBody=0;strokeColor=inherit;top=0;left=0;bottom=0;right=0;collapsible=0;dropTarget=0;fillColor=none;fontSize={FONT_SIZE};spacing=0;spacingLeft=5;spacingTop=1" parent="{{}}" vertex="1">
\t\t\t\t  <mxGeometry y="{{}}" width="{{}}" height="{{}}" as="geometry" />
\t\t\t\t</mxCell>
"""

BASE_CELL = f"""
\t\t\t\t<mxCell id="{{}}" value="{{}}" style="shape=partialRectangle;html=1;whiteSpace=wrap;align=left;verticalAlign=middle;strokeColor=inherit;overflow=hidden;fillColor=none;fontSize={FONT_SIZE};spacing=0;spacingLeft=5;spacingRight=5;spacingTop=1;spacingBottom=2" parent="{{}}" vertex="1">
\t\t\t\t  <mxGeometry x="{{}}" width="{{}}" height="{{}}" as="geometry" />
\t\t\t\t</mxCell>
"""

BASE_EDGE = """
\t\t\t\t<mxCell id="{}" style="edgeStyle=entityRelationEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" parent="x" source="{}" target="{}" edge="1">            
\t\t\t\t  <mxGeometry relative="1" as="geometry" />
\t\t\t\t</mxCell>
"""
