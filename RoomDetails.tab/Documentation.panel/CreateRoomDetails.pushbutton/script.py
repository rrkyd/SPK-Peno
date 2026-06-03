# -*- coding: utf-8 -*-
"""Create Room Details
Generate RCP, section, and 3D views for a room and place them on a sheet"""

__title__ = "Create Room\nDetails"
__author__ = "SPK"

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog, TaskDialogCommonButtons, TaskDialogResult
from pyrevit import forms, script
import json
import os
import math

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
output = script.get_output()


def get_config_file_path():
    """Get the path for the configuration JSON file"""
    doc_path = doc.PathName
    if not doc_path:
        return None
    doc_dir = os.path.dirname(doc_path)
    doc_name = os.path.splitext(os.path.basename(doc_path))[0]
    return os.path.join(doc_dir, "{}_room_details_config.json".format(doc_name))


def load_config():
    """Load configuration from JSON file"""
    config_path = get_config_file_path()
    if not config_path or not os.path.exists(config_path):
        TaskDialog.Show("Error", "Configuration file not found.\n\nPlease run 'Setup Config' first.")
        return None

    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        TaskDialog.Show("Error", "Failed to load configuration:\n\n{}".format(str(e)))
        return None


def validate_config(config):
    """Validate that all ElementIds in config still exist"""
    errors = []

    rcp_template = doc.GetElement(ElementId(int(config['rcp_view_template_id'])))
    if not rcp_template or not rcp_template.IsTemplate:
        errors.append("RCP view template no longer exists")

    section_template = doc.GetElement(ElementId(int(config['section_view_template_id'])))
    if not section_template or not section_template.IsTemplate:
        errors.append("Section view template no longer exists")

    view_3d_template = doc.GetElement(ElementId(int(config['view_3d_template_id'])))
    if not view_3d_template or not view_3d_template.IsTemplate:
        errors.append("3D view template no longer exists")

    titleblock = doc.GetElement(ElementId(int(config['titleblock_family_id'])))
    if not titleblock:
        errors.append("Titleblock family no longer exists")

    if errors:
        TaskDialog.Show("Configuration Error", "Configuration is invalid:\n\n" + "\n".join(errors) + "\n\nPlease run 'Setup Config' again.")
        return False

    return True


def get_scope_boxes():
    """Get all scope boxes in the project"""
    collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_VolumeOfInterest)
    scope_boxes = []
    for sb in collector:
        if isinstance(sb, Element):
            scope_boxes.append({
                'name': sb.Name,
                'element': sb
            })
    return sorted(scope_boxes, key=lambda x: x['name'])


def get_levels():
    """Get all levels sorted by elevation"""
    collector = FilteredElementCollector(doc).OfClass(Level)
    levels = []
    for level in collector:
        levels.append({
            'name': level.Name,
            'element': level,
            'elevation': level.Elevation
        })
    return sorted(levels, key=lambda x: x['elevation'])


def create_rcp_views(config, scope_box, levels):
    """Create RCP views for selected levels"""
    views = []
    room_name = config['default_room_name']
    rcp_template_id = ElementId(int(config['rcp_view_template_id']))

    for idx, level in enumerate(levels, start=1):
        view_name = "{}-{}-RCP-{:02d}".format(room_name, level['name'], idx)

        view_family_type_id = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewTypeCeilingPlan)
        rcp_view = ViewPlan.Create(doc, view_family_type_id, level['element'].Id)

        try:
            rcp_view.Name = view_name
        except:
            rcp_view.Name = "{}_001".format(view_name)

        rcp_view.ViewTemplateId = rcp_template_id

        bb = scope_box.get_BoundingBox(None)
        if bb:
            rcp_view.CropBoxActive = True
            rcp_view.CropBox = bb

        views.append(rcp_view)
        output.print_md("✓ Created RCP view: **{}**".format(rcp_view.Name))

    return views


def create_section_views(config, scope_box, levels, selected_edges):
    """Create section views for selected edges"""
    views = []
    room_name = config['default_room_name']
    section_depth = config['section_view_depth']
    section_template_id = ElementId(int(config['section_view_template_id']))

    bb = scope_box.get_BoundingBox(None)
    if not bb:
        return views

    min_pt = bb.Min
    max_pt = bb.Max

    section_configs = []

    if 'Top' in selected_edges:
        origin = XYZ((min_pt.X + max_pt.X) / 2, max_pt.Y - section_depth, (min_pt.Z + max_pt.Z) / 2)
        direction = XYZ(0, 1, 0)
        up = XYZ(0, 0, 1)
        section_configs.append(('Top', origin, direction, up))

    if 'Bottom' in selected_edges:
        origin = XYZ((min_pt.X + max_pt.X) / 2, min_pt.Y + section_depth, (min_pt.Z + max_pt.Z) / 2)
        direction = XYZ(0, -1, 0)
        up = XYZ(0, 0, 1)
        section_configs.append(('Bottom', origin, direction, up))

    if 'Right' in selected_edges:
        origin = XYZ(max_pt.X - section_depth, (min_pt.Y + max_pt.Y) / 2, (min_pt.Z + max_pt.Z) / 2)
        direction = XYZ(1, 0, 0)
        up = XYZ(0, 0, 1)
        section_configs.append(('Right', origin, direction, up))

    if 'Left' in selected_edges:
        origin = XYZ(min_pt.X + section_depth, (min_pt.Y + max_pt.Y) / 2, (min_pt.Z + max_pt.Z) / 2)
        direction = XYZ(-1, 0, 0)
        up = XYZ(0, 0, 1)
        section_configs.append(('Left', origin, direction, up))

    seq = 1
    for edge_name, origin, direction, up in section_configs:
        for level in levels:
            view_name = "{}-{}-Section-{:02d}".format(room_name, level['name'], seq)
            seq += 1

            view_family_type_id = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewTypeSection)

            transform = Transform.Identity
            transform.Origin = origin
            transform.BasisX = direction.CrossProduct(up).Normalize()
            transform.BasisY = up
            transform.BasisZ = direction.Negate()

            section_box = BoundingBoxXYZ()
            section_box.Transform = transform

            width = max_pt.X - min_pt.X if 'Top' in edge_name or 'Bottom' in edge_name else max_pt.Y - min_pt.Y
            height = max_pt.Z - min_pt.Z

            section_box.Min = XYZ(-width / 2, -height / 2, -section_depth / 10)
            section_box.Max = XYZ(width / 2, height / 2, section_depth)

            section_view = ViewSection.CreateSection(doc, view_family_type_id, section_box)

            try:
                section_view.Name = view_name
            except:
                section_view.Name = "{}_001".format(view_name)

            section_view.ViewTemplateId = section_template_id

            views.append(section_view)
            output.print_md("✓ Created Section view: **{}**".format(section_view.Name))

    return views


def create_3d_view(config, scope_box, levels):
    """Create isometric 3D view"""
    room_name = config['default_room_name']
    view_3d_template_id = ElementId(int(config['view_3d_template_id']))

    first_level_name = levels[0]['name']
    view_name = "{}-{}-3D-01".format(room_name, first_level_name)

    view_family_type_id = doc.GetDefaultElementTypeId(ElementTypeGroup.ViewType3D)
    view_3d = View3D.CreateIsometric(doc, view_family_type_id)

    try:
        view_3d.Name = view_name
    except:
        view_3d.Name = "{}_001".format(view_name)

    view_3d.ViewTemplateId = view_3d_template_id

    bb = scope_box.get_BoundingBox(None)
    if bb:
        view_3d.SetSectionBox(bb)

        center = XYZ(
            (bb.Min.X + bb.Max.X) / 2,
            (bb.Min.Y + bb.Max.Y) / 2,
            (bb.Min.Z + bb.Max.Z) / 2
        )

        width = bb.Max.X - bb.Min.X
        height = bb.Max.Y - bb.Min.Y
        depth = bb.Max.Z - bb.Min.Z
        distance = max(width, height, depth) * 2.0

        azimuth = math.radians(45)
        altitude = math.radians(35.264)

        cam_x = center.X + distance * math.cos(altitude) * math.cos(azimuth)
        cam_y = center.Y + distance * math.cos(altitude) * math.sin(azimuth)
        cam_z = center.Z + distance * math.sin(altitude)

        eye_position = XYZ(cam_x, cam_y, cam_z)
        forward_direction = (center - eye_position).Normalize()
        up_direction = XYZ(0, 0, 1)

        orientation = ViewOrientation3D(eye_position, up_direction, forward_direction)
        view_3d.SetOrientation(orientation)

    output.print_md("✓ Created 3D view: **{}**".format(view_3d.Name))
    return [view_3d]


def create_sheet_with_viewports(config, views, sheet_number, sheet_name):
    """Create sheet and place viewports using smart packing"""
    titleblock_id = ElementId(int(config['titleblock_family_id']))

    sheet = ViewSheet.Create(doc, titleblock_id)
    sheet.SheetNumber = sheet_number
    sheet.Name = sheet_name

    output.print_md("✓ Created sheet: **{} - {}**".format(sheet_number, sheet_name))

    titleblock = None
    for elem_id in sheet.GetAllViewports():
        elem = doc.GetElement(elem_id)
        if elem:
            titleblock = elem
            break

    if not titleblock:
        collector = FilteredElementCollector(doc, sheet.Id).OfCategory(BuiltInCategory.OST_TitleBlocks)
        for tb in collector:
            titleblock = tb
            break

    if titleblock:
        tb_bb = titleblock.get_BoundingBox(sheet)
        if tb_bb:
            margin = 25.0 / 304.8
            available_min = XYZ(tb_bb.Min.X + margin, tb_bb.Min.Y + margin, 0)
            available_max = XYZ(tb_bb.Max.X - margin, tb_bb.Max.Y - margin, 0)
        else:
            available_min = XYZ(0.5 / 304.8, 0.5 / 304.8, 0)
            available_max = XYZ(3.0, 2.0, 0)
    else:
        available_min = XYZ(0.5 / 304.8, 0.5 / 304.8, 0)
        available_max = XYZ(3.0, 2.0, 0)

    viewport_data = []
    for view in views:
        outline = view.Outline
        if outline:
            width = (outline.Max.U - outline.Min.U) * view.Scale / 304.8
            height = (outline.Max.V - outline.Min.V) * view.Scale / 304.8
        else:
            width = 0.5
            height = 0.5

        padding = 2.0 / 304.8
        viewport_data.append({
            'view': view,
            'width': width + padding,
            'height': height + padding,
            'area': (width + padding) * (height + padding)
        })

    viewport_data.sort(key=lambda x: x['area'], reverse=True)

    padding_between = 10.0 / 304.8
    current_x = available_min.X
    current_y = available_min.Y
    shelf_height = 0

    placed_count = 0
    for vp_data in viewport_data:
        if current_x + vp_data['width'] > available_max.X:
            current_x = available_min.X
            current_y += shelf_height + padding_between
            shelf_height = 0

        if current_y + vp_data['height'] > available_max.Y:
            output.print_md("⚠ Warning: Not all viewports fit on sheet. Placed {} of {} views.".format(placed_count, len(viewport_data)))
            break

        center_point = XYZ(
            current_x + vp_data['width'] / 2,
            current_y + vp_data['height'] / 2,
            0
        )

        try:
            viewport = Viewport.Create(doc, sheet.Id, vp_data['view'].Id, center_point)
            viewport.ChangeTypeId(doc.GetDefaultElementTypeId(ElementTypeGroup.ViewportType))
            placed_count += 1
            output.print_md("  ✓ Placed viewport: **{}**".format(vp_data['view'].Name))
        except Exception as e:
            output.print_md("  ⚠ Failed to place viewport for {}: {}".format(vp_data['view'].Name, str(e)))

        current_x += vp_data['width'] + padding_between
        shelf_height = max(shelf_height, vp_data['height'])

    if placed_count == len(viewport_data):
        output.print_md("✓ All {} viewports placed successfully".format(placed_count))

    return sheet


def main():
    config = load_config()
    if not config:
        return

    if not validate_config(config):
        return

    scope_boxes = get_scope_boxes()
    if not scope_boxes:
        TaskDialog.Show("Error", "No scope boxes found in the project.\n\nPlease create at least one scope box before running this script.")
        return

    selected_sb = forms.SelectFromList.show(
        [sb['name'] for sb in scope_boxes],
        title="Select Scope Box",
        button_name="Next",
        multiselect=False
    )
    if not selected_sb:
        return

    scope_box = next(sb['element'] for sb in scope_boxes if sb['name'] == selected_sb)

    all_levels = get_levels()
    if not all_levels:
        TaskDialog.Show("Error", "No levels found in the project.")
        return

    selected_level_names = forms.SelectFromList.show(
        [level['name'] for level in all_levels],
        title="Select Levels",
        button_name="Next",
        multiselect=True
    )
    if not selected_level_names:
        return

    selected_levels = [level for level in all_levels if level['name'] in selected_level_names]

    edge_options = ['Top', 'Bottom', 'Left', 'Right']
    selected_edges = forms.SelectFromList.show(
        edge_options,
        title="Select Section Edges",
        button_name="Next",
        multiselect=True
    )
    if not selected_edges:
        return

    sheet_number = forms.ask_for_string(
        prompt="Enter sheet number:",
        title="Sheet Number",
        default="A101"
    )
    if not sheet_number:
        return

    existing_sheet = None
    for sheet in FilteredElementCollector(doc).OfClass(ViewSheet):
        if sheet.SheetNumber == sheet_number:
            existing_sheet = sheet
            break

    if existing_sheet:
        TaskDialog.Show("Error", "Sheet number '{}' already exists.\n\nPlease use a different sheet number.".format(sheet_number))
        return

    sheet_name = forms.ask_for_string(
        prompt="Enter sheet name:",
        title="Sheet Name",
        default="Room Details"
    )
    if not sheet_name:
        return

    output.print_md("# Creating Room Details")
    output.print_md("---")

    t = Transaction(doc, "Create Room Details")
    t.Start()

    try:
        all_views = []

        output.print_md("## Creating RCP Views")
        rcp_views = create_rcp_views(config, scope_box, selected_levels)
        all_views.extend(rcp_views)

        output.print_md("\n## Creating Section Views")
        section_views = create_section_views(config, scope_box, selected_levels, selected_edges)
        all_views.extend(section_views)

        output.print_md("\n## Creating 3D View")
        view_3d = create_3d_view(config, scope_box, selected_levels)
        all_views.extend(view_3d)

        output.print_md("\n## Creating Sheet and Placing Viewports")
        sheet = create_sheet_with_viewports(config, all_views, sheet_number, sheet_name)

        t.Commit()

        output.print_md("\n---")
        output.print_md("# ✓ Room Details Created Successfully")
        output.print_md("**Sheet:** {} - {}".format(sheet_number, sheet_name))
        output.print_md("**Total Views:** {}".format(len(all_views)))
        output.print_md("  - RCP: {}".format(len(rcp_views)))
        output.print_md("  - Sections: {}".format(len(section_views)))
        output.print_md("  - 3D: {}".format(len(view_3d)))

    except Exception as e:
        t.RollBack()
        TaskDialog.Show("Error", "Failed to create room details:\n\n{}".format(str(e)))
        output.print_md("\n❌ **Error:** {}".format(str(e)))


if __name__ == '__main__':
    main()
