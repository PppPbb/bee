# Task Plan

Project title: **Cloud-Hive Bloomfield: A Procedural Honeycomb Resource System in Maya**

中文题目：**云上蜜源驱动的程序化蜂巢花田系统**

## Three-Person Division Of Work

### Person 1: Honeycomb And Data Model

- Design the hexagonal coordinate system.
- Generate honeycomb cells and neighbor relationships.
- Assign cell types.
- Implement nearest-cell mapping.
- Prepare pure Python tests or sample data for the honeycomb logic.
- Add Maya-only honeycomb geometry functions after the pure logic is stable.

### Person 2: Cloud Resources And Visual Style

- Define nectar and pollen resource drop data.
- Create cloud flower generation rules.
- Connect drops to honeycomb landing positions.
- Design the stylized look for clouds, flowers, resources, and cell materials.
- Implement Maya-only visual functions for drops, resource markers, and scene polish.

### Person 3: Bee Tasks, Animation, UI, And Integration

- Detect incorrect resource placement.
- Create transport and cleaning tasks.
- Implement BFS pathfinding.
- Animate bees and resources along paths in Maya.
- Build the Maya UI.
- Integrate modules through `code/main.py`.

## Suggested Development Phases

### Phase 1: Repository And Interface Setup

- Create the target folder structure.
- Define module responsibilities.
- Keep Maya-specific code separate from pure Python logic.
- Agree on shared data records for cells, drops, tasks, and bees.

### Phase 2: Pure Python MVP Logic

- Build the honeycomb graph.
- Assign cell types.
- Generate resource drop records.
- Map drops to cells.
- Detect wrong placements.
- Run BFS to find valid target cells.

### Phase 3: Maya Scene Construction

- Create honeycomb geometry.
- Add cloud flowers and nectar/pollen resource drops.
- Add materials and visual states.
- Draw path visualization.
- Animate bees and resource transfers.

### Phase 4: UI And Demonstration

- Add Maya UI controls.
- Add repeatable scene generation presets.
- Create camera, lights, and presentation framing.
- Capture screenshots and video.

### Phase 5: Final Report And Presentation

- Explain the system architecture.
- Show the core loop.
- Document the pure Python and Maya-specific split.
- Include final images, video links, and development screenshots.

## MVP Checklist

- [ ] Target repository structure exists.
- [ ] Pure Python honeycomb grid generation exists.
- [ ] Cell type assignment exists.
- [ ] Cloud resource generation exists.
- [ ] Resource drop mapping exists.
- [ ] Correct-cell validation exists.
- [ ] Task creation exists.
- [ ] BFS pathfinding exists.
- [ ] Maya honeycomb visualization exists.
- [ ] Maya cloud and resource visualization exists.
- [ ] Bee animation exists.
- [ ] Maya UI exists.
- [ ] Final visual direction reads as a honeycomb flower-field system, not a ground grassland or beehive prop scene.
- [ ] Final screenshots saved to `results/images/`.
- [ ] Final video saved to `results/video/`.
- [ ] Presentation materials saved to `presentation/`.
- [ ] Final report saved to `report/`.

## Final Outputs

- `presentation/`: final slide deck and any supporting presentation files.
- `report/`: written report, exported PDF, and source document if needed.
- `results/images/`: screenshots showing terrain, resource drops, BFS paths, bee movement, and final states.
- `results/video/`: rendered or screen-recorded demonstration video.
- `scenes/`: Maya scene files used for final demonstration.
