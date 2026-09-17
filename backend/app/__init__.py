"""FlyBrain Agent backend.

Connectome-grounded simulation API. See ../../SDD.md for the architecture.

Layering (a core product requirement, see NEUROSCIENCE.md section 7):
- BIOLOGICAL STRUCTURE   -> app.connectome, app.circuits
- COMPUTATIONAL DYNAMICS -> app.simulation
- APPLICATION DECODING   -> app.sensors, app.motor, app.behavior
- EMBODIMENT (P7.0)      -> app.embodiment (world / sensor / motor / body adapters, closed loop)
- THREAT LAB (P7.1)      -> app.api.embodiment (replayable closed-loop experiment API)
- API / WEB DEMO          -> app.api (serves the layers above; every payload carries the disclaimer)
"""

__version__ = "0.1.0"

#: Service identifier reported by ``GET /health``.
SERVICE_NAME = "flybrain-agent-backend"

#: Most recent phase of TASKS.md delivered in this codebase.
CURRENT_PHASE = "P7.1"

__all__ = ["CURRENT_PHASE", "SERVICE_NAME", "__version__"]
