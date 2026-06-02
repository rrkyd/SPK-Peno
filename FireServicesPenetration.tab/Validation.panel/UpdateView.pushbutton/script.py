# -*- coding: utf-8 -*-
"""Update Penetration Validation View
Refresh the validation 3D view with current penetration status"""

__title__ = "Update\nView"
__author__ = "SPK"

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import TaskDialog
from pyrevit import script

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

def find_validation_view():
    """Find the existing Penetration Validation view"""
    collector = FilteredElementCollector(doc).OfClass(View3D)

    for view in collector:
        if view.Name == "Penetration Validation":
            return view

    return None

def get_all_penetrations():
    """Get all Generic Model instances (penetrations)"""
    collector = FilteredElementCollector(doc)\
        .OfCategory(BuiltInCategory.OST_GenericModel)\
        .WhereElementIsNotElementType()

    return list(collector)

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
    """Check if penetration overlaps with MEP element"""
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

def update_view_overrides(view, penetrations, mep_elements):
    """Update the view overrides based on current status"""
    t = Transaction(doc, "Update Validation View")
    t.Start()

    try:
        output = script.get_output()
        output.print_md("## Analyzing {} penetrations...".format(len(penetrations)))

        pairs = []
        empty_penetrations = []

        for peno in penetrations:
            found_match = False
            for mep in mep_elements:
                if check_overlap(peno, mep):
                    pairs.append({'penetration_id': peno.Id, 'mep_id': mep.Id})
                    found_match = True
                    break

            if not found_match:
                empty_penetrations.append(peno)

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

        output.print_md("---")
        output.print_md("## Update Complete")
        output.print_md("- **Total Penetrations:** {}".format(len(penetrations)))
        output.print_md("- **Matched with MEP:** {}".format(len(pairs)))
        output.print_md("- **Empty (No MEP):** {}".format(len(empty_penetrations)))
        output.print_md("- **Match Rate:** {:.1f}%".format(
            100.0 * len(pairs) / len(penetrations) if penetrations else 0))

        uidoc.ActiveView = view
        uidoc.RefreshActiveView()

        return True
    except Exception as e:
        t.RollBack()
        TaskDialog.Show("Error", "Failed to update view: {}".format(str(e)))
        return False

def main():
    output = script.get_output()
    output.print_md("# Update Penetration Validation View")

    view = find_validation_view()
    if not view:
        TaskDialog.Show("Error",
            "Validation view not found. Please run 'Check Penetrations' first.")
        return

    output.print_md("**Found view:** {}".format(view.Name))

    output.print_md("## Getting elements...")
    penetrations = get_all_penetrations()
    mep_elements = get_mep_elements()

    output.print_md("**Penetrations:** {}".format(len(penetrations)))
    output.print_md("**MEP Elements:** {}".format(len(mep_elements)))

    update_view_overrides(view, penetrations, mep_elements)

if __name__ == '__main__':
    main()
