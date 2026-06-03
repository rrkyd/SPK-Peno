# Auto Room Detail Creator - Design Specification

**Date:** 2026-06-03  
**Author:** SPK  
**Status:** Approved

## Overview

A pyRevit extension that automates the creation of room detail documentation packages in Revit. The extension creates RCP views, section views, and 3D isometric views based on a scope box, then places them on a sheet with smart viewport packing.

## Architecture

### Extension Structure

```
RoomDetails.tab/
├── bundle.yaml
└── Documentation.panel/
    ├── bundle.yaml
    ├── SetupConfig.pushbutton/
    │   ├── icon.png
    │   └── script.py
    └── CreateRoomDetails.pushbutton/
        ├── icon.png
        └── script.py
```

### Configuration Storage

Configuration is stored per-project in a JSON file located at:
```
{rvt_directory}/{rvt_name}_room_details_config.json
```

This approach ensures:
- Configuration travels with the project when copied/shared
- No dependency on Revit project parameters
- Easy to edit manually if needed
- No pollution of project parameter namespace

### JSON Schema

```json
{
  "rcp_view_template_id": "123456",
  "section_view_template_id": "123457", 
  "view_3d_template_id": "123458",
  "default_room_name": "Meeting Room",
  "section_view_depth": 1000.0,
  "titleblock_family_id": "123459"
}
```

All ElementIds are stored as strings. Distances are in project units (typically mm).

## Component Design

### 1. Setup Configuration Script

**Purpose:** One-time or as-needed configuration of view templates and defaults.

**UI Flow:**

1. **RCP View Template Selection**
   - List all view templates filtered by `ViewFamily.CeilingPlan`
   - Single-select dropdown
   - Show template name
   - Validation: at least one template must exist

2. **Section View Template Selection**
   - List all view templates filtered by `ViewFamily.Section`
   - Single-select dropdown
   - Show template name
   - Validation: at least one template must exist

3. **3D View Template Selection**
   - List all view templates filtered by `ViewFamily.ThreeDimensional`
   - Single-select dropdown
   - Show template name
   - Validation: at least one template must exist

4. **Default Room Name**
   - Text input field
   - Default: "Room"
   - Used in view naming template
   - Validation: non-empty string

5. **Section View Depth**
   - Numeric input with unit label
   - Default: 1000mm (or project units)
   - Used for both:
     - Inward offset from scope box edge to section cut plane
     - Far clip distance from cut plane
   - Validation: positive number

6. **Default Titleblock**
   - List all titleblock families in project
   - Single-select dropdown
   - Show family name
   - Validation: at least one titleblock must exist

**Save Logic:**
- Write JSON to `{rvt_directory}/{rvt_name}_room_details_config.json`
- Show confirmation dialog with file path
- No transaction needed (external file write)

**Error Handling:**
- If RVT is not saved, prompt user to save first
- If directory is read-only, show error
- If no view templates exist for a required type, show specific error

### 2. Create Room Details Script

**Purpose:** Main workflow that creates views and sheets based on stored configuration.

#### Validation Phase

On script launch, before showing any dialogs:

1. Check JSON config file exists
   - If missing: show error, prompt to run Setup
   
2. Validate all ElementIds in config
   - Check each template ID exists and is valid view template
   - Check titleblock family ID exists and is valid titleblock
   - Show specific error for each missing element

3. If validation fails, exit with error message listing all issues

#### User Input Phase

**Dialog 1: Scope Box Selection**
- Dropdown list of all scope boxes in project
- Show scope box name
- Validation: at least one scope box must exist
- Button: "Next"

**Dialog 2: Level Selection**
- Multi-select checklist of all levels
- Show level name
- Sorted by elevation (lowest to highest)
- Validation: at least one level must be selected
- Buttons: "Back", "Next"

**Dialog 3: Section Edge Selection**
- Checkboxes for scope box edges:
  - [ ] Top edge
  - [ ] Bottom edge
  - [ ] Left edge
  - [ ] Right edge
- Show visual diagram indicating edge orientation
- Validation: at least one edge must be selected
- Buttons: "Back", "Next"

**Dialog 4: Sheet Information**
- Text input: Sheet Number
  - Validation: non-empty, doesn't exist in project
- Text input: Sheet Name
  - Validation: non-empty
- Buttons: "Back", "Create"

#### View Creation Phase

All view creation happens in a single transaction for atomicity.

**1. RCP Views**

For each selected level:
- View name: `{room_name}-{level_name}-RCP-{seq:02d}`
  - `room_name` from config
  - `level_name` from level
  - `seq` starts at 01, increments per level
- Create RCP view at level
- Apply RCP template from config
- Set crop box to scope box XY bounds
- Set crop box height to level elevation

**2. Section Views**

For each selected edge × each selected level:
- View name: `{room_name}-{level_name}-Section-{seq:02d}`
  - `seq` is global across all sections (01, 02, 03...)
- Determine section line placement:
  - Get scope box bounds
  - Offset inward from edge by `section_view_depth`
  - Orient parallel to edge
  - Direction: looking outward (away from scope box center)
- Create section view
- Apply section template from config
- Set far clip to `section_view_depth` from cut plane
- Set crop box to show selected level range

**3. 3D View**

Single 3D view:
- View name: `{room_name}-{level_name}-3D-{seq:02d}`
  - Use first selected level name
  - `seq` starts at 01
- Create 3D view
- Apply 3D template from config
- Set view orientation:
  - Camera position: outside scope box at 45° horizontal, 35.264° vertical
  - View direction: toward scope box center
  - This creates true isometric projection
- Set section box to scope box bounds (full height)

#### Sheet Creation and Viewport Placement Phase

**Sheet Creation:**
- Create new sheet with user-provided number and name
- Place titleblock from config at origin

**Smart Packing Algorithm:**

Uses a 2D bin-packing approach to arrange viewports efficiently:

1. **Calculate viewport dimensions** for each view:
   - Get view crop box width/height
   - Apply view scale
   - Add viewport border padding (2mm)
   - Result: viewport rectangle dimensions

2. **Sort viewports** by area (largest first):
   - Larger viewports placed first for better packing

3. **Shelf packing algorithm**:
   - Available space = titleblock bounds minus margin (25mm all sides)
   - Start first shelf at top-left of available space
   - For each viewport:
     - Try to place on current shelf (left to right)
     - If doesn't fit on shelf:
       - Start new shelf below current (shelf height = tallest viewport in shelf)
       - Place viewport at start of new shelf
     - Add 10mm padding between viewports
   - Continue until all viewports placed or space exhausted

4. **Collision detection**:
   - Track occupied rectangles on sheet
   - Before placing viewport, test for overlap with existing viewports
   - If collision detected, adjust position or fail with error

5. **Overflow handling**:
   - If all viewports don't fit, show warning with:
     - Number of viewports that fit
     - Number that didn't fit
     - Suggestion to use larger titleblock or fewer views
   - User can choose to proceed with partial placement or cancel

**Viewport Creation:**
- For each successfully placed position:
  - Create viewport at calculated XY position
  - Set viewport to reference view
  - Lock viewport position (prevent accidental dragging)

## Error Handling

### Configuration Errors

- **Missing config file**: Clear error message, direct to Setup script
- **Invalid ElementIds**: List each missing element by name and type
- **Corrupt JSON**: Show JSON parse error, suggest deleting file and re-running Setup
- **File permission errors**: Show specific OS error, suggest admin rights or different location

### User Input Errors

- **No scope boxes in project**: Error dialog, exit gracefully
- **No levels in project**: Error dialog, exit gracefully  
- **Sheet number exists**: Inline validation, re-prompt user
- **Invalid scope box bounds**: Zero-size or negative, error dialog

### View Creation Errors

- **View name collision**: Append suffix `_001`, `_002`, etc.
- **Template application fails**: Log warning, continue without template
- **Crop box exceeds limits**: Clamp to Revit's max/min bounds
- **Section line invalid**: Skip that section, log warning, continue

### Sheet Placement Errors

- **Titleblock placement fails**: Transaction rollback, show error
- **Insufficient sheet space**: Warning dialog with overflow details
- **Viewport creation fails**: Skip that viewport, log warning, continue with others

### Transaction Management

- All view creation in single transaction
- All sheet creation in single transaction  
- If sheet transaction fails, rollback everything (don't create orphan views)
- If view transaction fails, don't attempt sheet creation

## View Naming Convention

Template: `{room_name}-{level_name}-{view_type}-{sequence:02d}`

Examples:
- `Meeting Room-Level 1-RCP-01`
- `Meeting Room-Level 1-Section-01`
- `Meeting Room-Level 1-Section-02`
- `Meeting Room-Level 1-3D-01`

Sequence numbers:
- RCP views: independent sequence per level
- Section views: global sequence across all sections
- 3D views: independent sequence (typically just 01)

## Section View Geometry

### Placement Logic

For a scope box with bounds `min_point` and `max_point`:

**Top edge (max Y):**
- Cut plane at: `y = max_point.Y - section_view_depth`
- Parallel to X axis
- Direction: +Y (looking outward/north)

**Bottom edge (min Y):**
- Cut plane at: `y = min_point.Y + section_view_depth`
- Parallel to X axis
- Direction: -Y (looking outward/south)

**Right edge (max X):**
- Cut plane at: `x = max_point.X - section_view_depth`
- Parallel to Y axis
- Direction: +X (looking outward/east)

**Left edge (min X):**
- Cut plane at: `x = min_point.X + section_view_depth`
- Parallel to Y axis
- Direction: -X (looking outward/west)

### Far Clip Distance

Far clip is set to `section_view_depth` from the cut plane in the view direction (outward).

This means:
- Cut plane offset inward: `section_view_depth`
- View depth outward: `section_view_depth`
- Total view captures: `2 × section_view_depth` of scope box width

## 3D View Geometry

### Isometric Orientation

True isometric projection requires:
- **Horizontal rotation**: 45° (azimuth)
- **Vertical rotation**: 35.264° (altitude)
  - Derived from: `arctan(1/√2) ≈ 35.264°`

### Camera Position Calculation

For scope box center at `(cx, cy, cz)` and bounds size `(w, h, d)`:

1. Calculate distance from center to camera:
   - `distance = max(w, h, d) × 2.0` (ensures full box is visible)

2. Calculate camera position in spherical coordinates:
   - `cam_x = cx + distance × cos(35.264°) × cos(45°)`
   - `cam_y = cy + distance × cos(35.264°) × sin(45°)`
   - `cam_z = cz + distance × sin(35.264°)`

3. View direction vector:
   - From camera position toward scope box center
   - Normalized: `(cx - cam_x, cy - cam_y, cz - cam_z) / ||vector||`

4. Up vector:
   - Standard: `(0, 0, 1)` (Z-up in Revit)

### Section Box

Set 3D view section box to exactly match scope box bounds. This crops the view to show only the scope box volume.

## Data Flow

```
Setup Script
    ↓
[Save to JSON] ← {rvt_dir}/{rvt_name}_room_details_config.json
    ↓
Create Room Details Script
    ↓
[Load JSON]
    ↓
[Validate ElementIds]
    ↓
[User Input Dialogs] → Scope Box, Levels, Edges, Sheet Info
    ↓
[Transaction: Create Views]
    ├─ RCP Views (per level)
    ├─ Section Views (per edge × level)
    └─ 3D View
    ↓
[Transaction: Create Sheet + Viewports]
    ├─ Create Sheet
    ├─ Place Titleblock
    ├─ Calculate Viewport Layout (smart packing)
    └─ Place Viewports
    ↓
[Show Summary] → Count of views/viewports created
```

## Dependencies

### Revit API
- `Autodesk.Revit.DB`: Core database access
  - `ViewPlan`, `ViewSection`, `View3D`
  - `ViewFamilyType`, `ElementId`
  - `BoundingBoxXYZ`, `XYZ`, `Transform`
  - `Transaction`, `FilteredElementCollector`
  - `FamilySymbol` (titleblocks)

### pyRevit
- `pyrevit.forms`: UI dialogs
  - `SelectFromList`
  - `alert`, `ask_for_string`
- `pyrevit.script`: Output window

### Python Standard Library
- `json`: Config file serialization
- `os.path`: File path operations
- `math`: Trigonometry for 3D camera position

## Testing Strategy

### Unit-level Tests (Manual)

**Setup Script:**
1. Run on project with no view templates → expect specific errors
2. Run on project with templates → expect successful save
3. Verify JSON file contents match selections
4. Edit JSON manually, reload → verify values applied

**Config Validation:**
1. Delete config file → expect error with prompt to run Setup
2. Corrupt JSON syntax → expect JSON parse error
3. Delete view template → expect specific error naming template
4. Change ElementId to invalid → expect validation error

**View Creation:**
1. Single level + single edge → expect 3 views (RCP, Section, 3D)
2. Multiple levels + multiple edges → expect correct count
3. View names follow convention → verify manually
4. Section offset from edge → measure in model

**Sheet Placement:**
1. Small titleblock + many views → expect overflow warning
2. Large titleblock + few views → expect all placed
3. Viewport spacing → measure in sheet view (should be ~10mm)
4. Viewport collision detection → verify no overlaps

### Integration Tests (Manual Workflow)

**Full Happy Path:**
1. New project with scope box, levels, templates, titleblock
2. Run Setup → select templates, set room name, set depth, select titleblock
3. Verify JSON file created and contains correct data
4. Run Create Room Details → select scope box, levels, edges, sheet info
5. Verify views created with correct names and templates
6. Verify sheet created with viewports arranged properly
7. Open each view → verify geometry matches expectations

**Error Recovery:**
1. Start Create Room Details, cancel at level selection → expect no changes
2. Delete titleblock mid-run → expect transaction rollback
3. Insufficient sheet space → accept partial placement, verify correct count

**Configuration Changes:**
1. Run Setup with one room name → create views
2. Run Setup again with different room name → create new views
3. Verify both sets of views exist with different names

## Future Enhancements (Out of Scope)

- Multi-room batch processing (iterate over list of scope boxes)
- Custom viewport arrangement templates (user-defined layouts)
- View filtering by category (show/hide specific elements)
- Automatic viewport scaling to fit sheet optimally
- Duplicate sheet detection and auto-increment
- Export view list to Excel
- Integration with room schedules (pull room names from schedule)

## Success Criteria

The extension is successful if:

1. **Usability**: User can create a complete room documentation package (RCP, sections, 3D, sheet) in under 2 minutes after initial setup
2. **Reliability**: Handles common error cases gracefully without crashing Revit
3. **Correctness**: Views show correct geometry (scope box bounds, section offsets, isometric angle)
4. **Flexibility**: Configuration survives project copies, template changes, and manual edits
5. **Efficiency**: Smart packing maximizes sheet usage without viewport overlaps
