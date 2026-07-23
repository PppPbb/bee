"""Shared pure Python configuration for Cloud-Hive Meadow."""


DEFAULT_INTEGRATION_PARAMETERS = {
    "hive": {
        "size": 3,
        "cell_size": 1.0,
        "honey_ratio": 0.3,
        "pollen_ratio": 0.3,
        "empty_ratio": 0.3,
        "capped_ratio": 0.1,
        "seed": 42,
    },
    "clouds": {
        "cloud_count": 3,
        "scene_radius": 5.0,
        "min_height": 4.0,
        "max_height": 6.0,
        "nectar_amount": 0.8,
        "pollen_amount": 0.6,
        "seed": 10,
    },
    "drops": {
        "nectar_drop_rate": 3,
        "pollen_drop_rate": 3,
        "wind_strength": 1.0,
        "wind_direction_degrees": 45.0,
        "spread_radius": 1.2,
        "seed": 20,
    },
    "bees": {
        "bee_count": 3,
        "start_position": [0.0, 0.8, 0.0],
    },
    "tasks": {
        "max_tasks_to_complete": 999,
    },
    "resources": {
        "consumption_per_cycle": 0.05,
        "collection_thresholds": {
            "nectar": 1.5,
            "pollen": 1.2,
        },
        "collection_amount": 0.4,
    },
    "simulation": {
        "cycle": 0,
    },
    "visual": {
        "ground_radius": 9.0,
        "cell_depth": 0.35,
        "voxel_density": 14,
        "cloud_scale": 0.85,
        "flowers_per_cloud": 7,
        "bee_scale": 1.0,
        "background_seed": 77,
        "animation_end": 320,
        "drop_fall_frames": 64,
        "bee_frame_step": 22,
        "frame_duration_multiplier": 4.0,
        # 0 disables the optional presentation cap and uses every available bee.
        "demo_max_active_bees": 0,
        "show_paths": True,
        "show_demo_guide": True,
        "show_demo_legend": True,
        "show_demo_stage_hint": True,
        "render_background": True,
    },
}
