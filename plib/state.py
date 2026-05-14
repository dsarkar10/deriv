from enum import Enum, auto


class PipelineStage(Enum):
    INIT = auto()
    STRATEGIES_LOADED = auto()
    DATA_FETCHED_OR_SIMULATED = auto()
    STRATEGIES_FORMALISED = auto()
    SPECS_VALIDATED = auto()
    BACKTESTS_EXECUTED = auto()
    LEDGERS_WRITTEN = auto()
    METRICS_COMPUTED = auto()
    STRATEGIES_CRITIQUED = auto()
    OPTIONAL_ROBUSTNESS_TESTS_COMPLETE = auto()
    REPORT_GENERATED = auto()
    VALIDATION_COMPLETE = auto()
    RESULTS_FINALISED = auto()


_STAGE_ORDER = list(PipelineStage)


class Pipeline:
    def __init__(self):
        self.current_stage = PipelineStage.INIT
        self._stage_index = 0

    @property
    def stage_index(self):
        return _STAGE_ORDER.index(self.current_stage)

    def transition(self, target: PipelineStage):
        target_idx = _STAGE_ORDER.index(target)
        expected_idx = self.stage_index + 1
        if target_idx != expected_idx:
            allowed = _STAGE_ORDER[expected_idx].name if expected_idx < len(_STAGE_ORDER) else "None"
            raise ValueError(
                f"Cannot transition to {target.name}. "
                f"Expected next stage: {allowed}. "
                f"Current stage: {self.current_stage.name}"
            )
        self.current_stage = target

    def assert_at_least(self, stage: PipelineStage):
        if self.stage_index < _STAGE_ORDER.index(stage):
            raise RuntimeError(
                f"Pipeline must be at stage {stage.name} or later, "
                f"currently at {self.current_stage.name}"
            )

    def assert_exactly(self, stage: PipelineStage):
        if self.current_stage != stage:
            raise RuntimeError(
                f"Pipeline must be exactly at stage {stage.name}, "
                f"currently at {self.current_stage.name}"
            )
