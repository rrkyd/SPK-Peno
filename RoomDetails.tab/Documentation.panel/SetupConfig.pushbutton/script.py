# -*- coding: utf-8 -*-
"""Setup Configuration for Room Details
Configure view templates, room name, section depth, and titleblock"""

__title__ = "Setup\nConfig"
__author__ = "SPK"

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog
from pyrevit import forms, script
import json
import os

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def get_view_templates_by_type(view_family):
    """Get all view templates of a specific type"""
    collector = FilteredElementCollector(doc).OfClass(View)
    templates = []

    for view in collector:
        if view.IsTemplate and view.ViewType == view_family:
            templates.append({
                'name': view.Name,
                'id': view.Id.ToString()
            })

    return sorted(templates, key=lambda x: x['name'])


def get_titleblock_families():
    """Get all titleblock families in the project"""
    collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_TitleBlocks).WhereElementIsElementType()
    titleblocks = []

    for tb in collector:
        if isinstance(tb, FamilySymbol):
            titleblocks.append({
                'name': tb.FamilyName + " : " + tb.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString(),
                'id': tb.Id.ToString()
            })

    return sorted(titleblocks, key=lambda x: x['name'])


def get_config_file_path():
    """Get the path for the configuration JSON file"""
    doc_path = doc.PathName

    if not doc_path:
        TaskDialog.Show("Error", "Please save the Revit project before running Setup.")
        return None

    doc_dir = os.path.dirname(doc_path)
    doc_name = os.path.splitext(os.path.basename(doc_path))[0]
    config_path = os.path.join(doc_dir, "{}_room_details_config.json".format(doc_name))

    return config_path


def main():
    # Check if document is saved
    config_path = get_config_file_path()
    if not config_path:
        return

    # Get RCP view templates
    rcp_templates = get_view_templates_by_type(ViewType.CeilingPlan)
    if not rcp_templates:
        TaskDialog.Show("Error", "No RCP (Ceiling Plan) view templates found in the project.\n\nPlease create at least one RCP view template before running Setup.")
        return

    # Get Section view templates
    section_templates = get_view_templates_by_type(ViewType.Section)
    if not section_templates:
        TaskDialog.Show("Error", "No Section view templates found in the project.\n\nPlease create at least one Section view template before running Setup.")
        return

    # Get 3D view templates
    view_3d_templates = get_view_templates_by_type(ViewType.ThreeD)
    if not view_3d_templates:
        TaskDialog.Show("Error", "No 3D view templates found in the project.\n\nPlease create at least one 3D view template before running Setup.")
        return

    # Get titleblocks
    titleblocks = get_titleblock_families()
    if not titleblocks:
        TaskDialog.Show("Error", "No titleblock families found in the project.\n\nPlease load at least one titleblock family before running Setup.")
        return

    # Load existing config if available
    existing_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                existing_config = json.load(f)
        except:
            pass

    # Select RCP view template
    rcp_options = [t['name'] for t in rcp_templates]
    selected_rcp = forms.SelectFromList.show(
        rcp_options,
        title="Select RCP View Template",
        button_name="Select",
        multiselect=False
    )
    if not selected_rcp:
        return

    rcp_template_id = next(t['id'] for t in rcp_templates if t['name'] == selected_rcp)

    # Select Section view template
    section_options = [t['name'] for t in section_templates]
    selected_section = forms.SelectFromList.show(
        section_options,
        title="Select Section View Template",
        button_name="Select",
        multiselect=False
    )
    if not selected_section:
        return

    section_template_id = next(t['id'] for t in section_templates if t['name'] == selected_section)

    # Select 3D view template
    view_3d_options = [t['name'] for t in view_3d_templates]
    selected_3d = forms.SelectFromList.show(
        view_3d_options,
        title="Select 3D View Template",
        button_name="Select",
        multiselect=False
    )
    if not selected_3d:
        return

    view_3d_template_id = next(t['id'] for t in view_3d_templates if t['name'] == selected_3d)

    # Input default room name
    default_room_name = existing_config.get('default_room_name', 'Room')
    room_name = forms.ask_for_string(
        default=default_room_name,
        prompt="Enter default room name for view naming:",
        title="Room Name"
    )
    if not room_name:
        return

    # Input section view depth
    default_depth = existing_config.get('section_view_depth', 1000.0)
    depth_str = forms.ask_for_string(
        default=str(default_depth),
        prompt="Enter section view depth (project units):\n(Used for offset from edge and far clip distance)",
        title="Section View Depth"
    )
    if not depth_str:
        return

    try:
        section_view_depth = float(depth_str)
        if section_view_depth <= 0:
            TaskDialog.Show("Error", "Section view depth must be a positive number.")
            return
    except ValueError:
        TaskDialog.Show("Error", "Invalid number format for section view depth.")
        return

    # Select titleblock
    tb_options = [tb['name'] for tb in titleblocks]
    selected_tb = forms.SelectFromList.show(
        tb_options,
        title="Select Default Titleblock",
        button_name="Select",
        multiselect=False
    )
    if not selected_tb:
        return

    titleblock_id = next(tb['id'] for tb in titleblocks if tb['name'] == selected_tb)

    # Create configuration dictionary
    config = {
        'rcp_view_template_id': rcp_template_id,
        'section_view_template_id': section_template_id,
        'view_3d_template_id': view_3d_template_id,
        'default_room_name': room_name,
        'section_view_depth': section_view_depth,
        'titleblock_family_id': titleblock_id
    }

    # Save configuration to JSON file
    try:
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)

        TaskDialog.Show(
            "Success",
            "Configuration saved successfully to:\n\n{}\n\nYou can now run 'Create Room Details' to generate views and sheets.".format(config_path)
        )
    except Exception as e:
        TaskDialog.Show("Error", "Failed to save configuration file:\n\n{}".format(str(e)))


if __name__ == '__main__':
    main()
