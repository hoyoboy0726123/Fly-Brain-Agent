"""FlyBrain Agent backend.

Connectome-grounded simulation API. See ../../SDD.md for the architecture.

Layering (a core product requirement, see NEUROSCIENCE.md section 7):
- BIOLOGICAL STRUCTURE   -> app.connectome, app.circuits
- COMPUTATIONAL DYNAMICS -> app.simulation
- APPLICATION DECODING   -> app.sensors, app.motor
"""

__version__ = "0.0.1"

#: Service identifier reported by ``GET /health``.
SERVICE_NAME = "flybrain-agent-backend"

#: Most recent phase of TASKS.md delivered in this codebase.
CURRENT_PHASE = "P0"

__all__ = ["CURRENT_PHASE", "SERVICE_NAME", "__version__"]
