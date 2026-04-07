class Team:
    def __init__(
        self,
        pass_reliability,
        pass_under_pressure,
        shot_conversion,
        xg_per_shot,
        ball_retention,
        pressure_success,
        pressure_aggression,
    ):

        self.pass_reliability = pass_reliability
        self.pass_under_pressure = pass_under_pressure
        self.shot_conversion = shot_conversion
        self.xg_per_shot = xg_per_shot
        self.ball_retention = ball_retention
        self.pressure_success = pressure_success
        self.pressure_aggression = pressure_aggression
        return
