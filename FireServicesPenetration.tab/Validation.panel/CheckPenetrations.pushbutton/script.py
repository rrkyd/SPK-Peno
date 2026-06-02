# -*- coding: utf-8 -*-
"""Check Fire Services Penetrations
Validate penetrations overlap with pipes/cable trays/conduits"""

__title__ = "Check\nPenetrations"
__author__ = "SPK"

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog
from pyrevit import forms, script
import clr

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

def get_generic_model_families():
    """Get all Generic Model families and their types"""
    collector = FilteredElementCollector(doc).OfClass(Family)
    families_dict = {}

    for family in collector:
        if family.FamilyCategory and family.FamilyCategory.Name == "Generic Models":
            symbol_ids = family.GetFamilySymbolIds()

            if symbol_ids.Count > 0:
                types_list = []
                for symbol_id in symbol_ids:
                    symbol = doc.GetElement(symbol_id)
                    types_list.append({
                        'name': symbol.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM).AsString(),
                        'id': symbol_id
                    })

                families_dict[family.Name] = {
                    'family_id': family.Id,
                    'types': types_list
                }

    return families_dict

def select_penetration_types():
    """Prompt user to select penetration family types"""
    families = get_generic_model_families()

    if not families:
        TaskDialog.Show("Error", "No Generic Model families found in the project.")
        return None

    options = []
    for family_name, data in sorted(families.items()):
        for type_data in data['types']:
            options.append({
                'display': "{} : {}".format(family_name, type_data['name']),
                'type_id': type_data['id']
            })

    selected = forms.SelectFromList.show(
        [opt['display'] for opt in options],
        title='Select Penetration Types',
        multiselect=True,
        button_name='Select'
    )

    if not selected:
        return None

    selected_ids = [opt['type_id'] for opt in options if opt['display'] in selected]
    return selected_ids

def get_penetration_instances(type_ids):
    """Get all instances of selected penetration types"""
    instances = []

    for type_id in type_ids:
        collector = FilteredElementCollector(doc)\
            .OfClass(FamilyInstance)\
            .WhereElementIsNotElementType()

        for elem in collector:
            if elem.GetTypeId() == type_id:
                instances.append(elem)

    return instances

def get_mep_elements():
    """Get all pipes, cable trays, and conduits"""
    mep_elements = []

    pipes = FilteredElementCollector(doc).OfClass(Pipe).WhereElementIsNotElementType().ToElements()
    mep_elements.extend(pipes)

    cable_trays = FilteredElementCollector(doc).OfClass(CableTray).WhereElementIsNotElementType().ToElements()
    mep_elements.extend(cable_trays)

    conduits = FilteredElementCollector(doc).OfClass(Conduit).WhereElementIsNotElementType().ToElements()
    mep_elements.extend(conduits)

    return mep_elements

def check_overlap(penetration, mep_element):
    """Check if penetration overlaps with MEP element using bounding boxes"""
    try:
        peno_bb = penetration.get_BoundingBox(None)
        mep_bb = mep_element.get_BoundingBox(None)

        if not peno_bb or not mep_bb:
            return False

        tolerance = 0.1

        x_overlap = (peno_bb.Min.X - tolerance <= mep_bb.Max.X and
                     peno_bb.Max.X + tolerance >= mep_bb.Min.X)
        y_overlap = (peno_bb.Min.Y - tolerance <= mep_bb.Max.Y and
                     peno_bb.Max.Y + tolerance >= mep_bb.Min.Y)
        z_overlap = (peno_bb.Min.Z - tolerance <= mep_bb.Max.Z and
                     peno_bb.Max.Z + tolerance >= mep_bb.Min.Z)

        return x_overlap and y_overlap and z_overlap
    except:
        return False

def find_penetration_pairs(penetrations, mep_elements):
    """Find pairs of penetrations and overlapping MEP elements"""
    pairs = []
    empty_penetrations = []

    output = script.get_output()
    output.print_md("## Checking {} penetrations against {} MEP elements...".format(
        len(penetrations), len(mep_elements)))

    for peno in penetrations:
        found_match = False
        for mep in mep_elements:
            if check_overlap(peno, mep):
                pairs.append({
                    'penetration_id': peno.Id,
                    'mep_id': mep.Id,
                    'penetration': peno,
                    'mep': mep
                })
                found_match = True
                break

        if not found_match:
            empty_penetrations.append(peno)

    output.print_md("**Found {} matched pairs**".format(len(pairs)))
    output.print_md("**Found {} empty penetrations**".format(len(empty_penetrations)))

    return pairs, empty_penetrations

def create_schedule(pairs):
    """Create a schedule showing penetration-MEP pairs"""
    t = Transaction(doc, "Create Penetration Schedule")
    t.Start()

    try:
        schedule = ViewSchedule.CreateSchedule(doc, ElementId(BuiltInCategory.OST_GenericModel))
        schedule.Name = "Fire Services Penetration Validation"

        definition = schedule.Definition

        definition.AddField(ScheduleFieldType.Instance, ElementId(BuiltInParameter.ELEM_FAMILY_AND_TYPE_PARAM))
        definition.AddField(ScheduleFieldType.Instance, ElementId(BuiltInParameter.ELEM_FAMILY_PARAM))
        definition.AddField(ScheduleFieldType.Instance, ElementId(BuiltInParameter.ALL_MODEL_MARK))

        t.Commit()

        output = script.get_output()
        output.print_md("**Schedule created:** {}".format(schedule.Name))

        return schedule
    except Exception as e:
        t.RollBack()
        TaskDialog.Show("Error", "Failed to create schedule: {}".format(str(e)))
        return None

def create_validation_view(pairs, empty_penetrations, mep_elements):
    """Create 3D view with transparency overrides"""
    t = Transaction(doc, "Create Validation 3D View")
    t.Start()

    try:
        view_family_types = FilteredElementCollector(doc).OfClass(ViewFamilyType)
        view_3d_type = None
        for vft in view_family_types:
            if vft.ViewFamily == ViewFamily.ThreeDimensional:
                view_3d_type = vft
                break

        if not view_3d_type:
            TaskDialog.Show("Error", "No 3D view type found")
            t.RollBack()
            return None

        view = View3D.CreateIsometric(doc, view_3d_type.Id)
        view.Name = "Penetration Validation"
        view.DetailLevel = ViewDetailLevel.Fine

        ogs_matched = OverrideGraphicSettings()
        ogs_matched.SetProjectionLineColor(Color(0, 255, 0))
        ogs_matched.SetSurfaceTransparency(0)

        ogs_empty = OverrideGraphicSettings()
        ogs_empty.SetProjectionLineColor(Color(255, 0, 0))
        ogs_empty.SetSurfaceForegroundPatternColor(Color(255, 0, 0))
        ogs_empty.SetSurfaceTransparency(0)

        ogs_unmatched_mep = OverrideGraphicSettings()
        ogs_unmatched_mep.SetSurfaceTransparency(90)

        matched_mep_ids = set(pair['mep_id'].IntegerValue for pair in pairs)

        for pair in pairs:
            view.SetElementOverrides(pair['penetration_id'], ogs_matched)

        for peno in empty_penetrations:
            view.SetElementOverrides(peno.Id, ogs_empty)

        for mep in mep_elements:
            if mep.Id.IntegerValue not in matched_mep_ids:
                view.SetElementOverrides(mep.Id, ogs_unmatched_mep)

        t.Commit()

        output = script.get_output()
        output.print_md("**3D View created:** {}".format(view.Name))
        output.print_md("- **Green:** Matched penetrations")
        output.print_md("- **Red:** Empty penetrations")
        output.print_md("- **90% Transparent:** Unmatched MEP elements")

        return view
    except Exception as e:
        t.RollBack()
        TaskDialog.Show("Error", "Failed to create 3D view: {}".format(str(e)))
        return None

def save_validation_data(pairs, empty_penetrations):
    """Save validation data to shared parameters for tracking"""
    t = Transaction(doc, "Save Validation Data")
    t.Start()

    try:
        proj_info = doc.ProjectInformation

        param = proj_info.get_Parameter(BuiltInParameter.PROJECT_COMMENTS)
        if param and not param.IsReadOnly:
            param.Set("Matched:{} Empty:{}".format(len(pairs), len(empty_penetrations)))

        t.Commit()
    except:
        t.RollBack()

def main():
    output = script.get_output()
    output.print_md("# Fire Services Penetration Validation")

    selected_types = select_penetration_types()
    if not selected_types:
        output.print_md("**Cancelled:** No penetration types selected")
        return

    output.print_md("## Step 1: Getting penetration instances...")
    penetrations = get_penetration_instances(selected_types)

    if not penetrations:
        TaskDialog.Show("Info", "No penetration instances found for selected types.")
        return

    output.print_md("**Found {} penetrations**".format(len(penetrations)))

    output.print_md("## Step 2: Getting MEP elements...")
    mep_elements = get_mep_elements()
    output.print_md("**Found {} MEP elements**".format(len(mep_elements)))

    output.print_md("## Step 3: Checking overlaps...")
    pairs, empty_penetrations = find_penetration_pairs(penetrations, mep_elements)

    output.print_md("## Step 4: Creating schedule...")
    schedule = create_schedule(pairs)

    output.print_md("## Step 5: Creating 3D validation view...")
    view = create_validation_view(pairs, empty_penetrations, mep_elements)

    output.print_md("## Step 6: Saving validation data...")
    save_validation_data(pairs, empty_penetrations)

    output.print_md("---")
    output.print_md("## Summary")
    output.print_md("- **Total Penetrations:** {}".format(len(penetrations)))
    output.print_md("- **Matched with MEP:** {}".format(len(pairs)))
    output.print_md("- **Empty (No MEP):** {}".format(len(empty_penetrations)))
    output.print_md("- **Match Rate:** {:.1f}%".format(
        100.0 * len(pairs) / len(penetrations) if penetrations else 0))

if __name__ == '__main__':
    main()
