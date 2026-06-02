# Fire Services Penetration Validation

pyRevit extension for validating fire services penetrations in Revit models.

## Features

### 1. Check Penetrations
- **Prompts user to select** penetration families and types from Generic Models
- **Detects overlaps** between penetrations and MEP elements (pipes, cable trays, conduits)
- **Creates a schedule** showing matched penetration-MEP pairs
- **Generates a 3D validation view** with color-coded visualization:
  - **Green**: Penetrations matched with MEP elements
  - **Red**: Empty penetrations (no MEP overlap)
  - **90% Transparent**: Unmatched MEP elements
- **Tracks validation status** in project information

### 2. Update View
- **Refreshes** the validation 3D view with current penetration status
- **Recalculates** all overlaps and updates visual overrides
- **Shows updated statistics** on match rates

## Installation

1. Copy the `FireServicesPenetration.tab` folder to your pyRevit extensions directory:
   - Typically: `%APPDATA%\pyRevit\Extensions`
   - Or your custom extensions path

2. Reload pyRevit or restart Revit

## Usage

### First Time Setup
1. Click **"Check Penetrations"** button in the Fire Services tab
2. Select the penetration family types you want to validate
3. The script will:
   - Find all instances of selected types
   - Check for overlaps with pipes/cable trays/conduits
   - Create a schedule named "Fire Services Penetration Validation"
   - Create a 3D view named "Penetration Validation"
   - Display summary statistics

### Updating After Changes
1. Make changes to penetrations or MEP elements in your model
2. Click **"Update View"** button
3. The validation view will refresh with current status

## Technical Details

### Overlap Detection
- Uses bounding box intersection with 0.1 unit tolerance
- Checks 3D overlap in X, Y, and Z axes
- Each penetration is matched with first overlapping MEP element

### MEP Element Categories
- Pipes (`OST_PipeCurves`)
- Cable Trays (`OST_CableTray`)
- Conduits (`OST_Conduit`)

### Visualization
- **Matched penetrations**: Green color, no transparency
- **Empty penetrations**: Red color, no transparency
- **Unmatched MEP**: 90% transparent (nearly invisible)

## Requirements

- Autodesk Revit 2019 or later
- pyRevit installed and configured
- Generic Model families for penetrations
- MEP elements in the model

## Author

SPK

## License

See LICENSE file
