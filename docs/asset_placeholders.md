# Asset Placeholder Plan

Project concept: **Cloud-Hive Bloomfield**, a honeycomb flower-field resource system.

Use this file to track future model replacement.

| Asset | Current Placeholder | Future Model Notes |
| --- | --- | --- |
| Bee | Small yellow cuboid with dark stripe | Replace with stylized bee mesh; keep pivot centered. |
| Cloud | Random three-tone merged voxel volume | Tune lobe count, seed, or palette only; no fixed cloud model is required. |
| Nectar | Shared glossy voxel instance with glint instances | Tune animation timing or palette only; no texture asset is required. |
| Pollen | Three-color shared voxel instances | Tune grain count or palette only; no texture asset is required. |
| Honey Cell | Merged texture-free voxel shell and honey pool | Keep discrete fill levels and pixel highlights. |
| Pollen Cell | Merged voxel shell with instanced grains | Keep grain transforms instanced from shared cube prototypes. |
| Capped Cell | Merged cream voxel plate | Keep its visibility keyed to the delivery frame. |
| Honeycomb Field Accent | Simple procedural marker if needed | Keep decorative accents secondary to cloud flowers, honeycomb cells, drops, and bee paths. |

Keep replacement assets near Maya scene scale:

- One honeycomb cell radius is usually `1.0`.
- Bee placeholder length is about `0.55`.
- Resource drops are about `0.12`.
