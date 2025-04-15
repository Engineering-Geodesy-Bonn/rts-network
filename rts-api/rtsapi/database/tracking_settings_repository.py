import logging

from fastapi import Depends
from sqlalchemy.orm import Session

from rtsapi.database.models import TrackingSettings
from rtsapi.dependencies import get_db
from rtsapi.exceptions import TrackingSettingsNotFoundException

logger = logging.getLogger("root")


class TrackingSettingsRepository:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def create_tracking_settings(self, tracking_settings: TrackingSettings) -> TrackingSettings:
        self.db.query(TrackingSettings).filter_by(
            rts_id=tracking_settings.rts_id
        ).delete()  # delete existing tracking settings
        self.db.commit()
        self.db.add(tracking_settings)
        self.db.commit()
        self.db.refresh(tracking_settings)
        return tracking_settings

    def delete_tracking_settings(self, rts_id: int) -> None:
        self.db.query(TrackingSettings).filter_by(rts_id=rts_id).delete()
        self.db.commit()

    def get_tracking_settings(self, rts_id: int) -> TrackingSettings:
        tracking_settings = self.db.query(TrackingSettings).filter(TrackingSettings.rts_id == rts_id).first()

        if tracking_settings is None:
            raise TrackingSettingsNotFoundException(rts_id)

        return tracking_settings

    def get_all_tracking_settings(self) -> list[TrackingSettings]:
        return self.db.query(TrackingSettings).all()

    def update_tracking_settings(self, rts_id: int, tracking_settings: TrackingSettings) -> TrackingSettings:
        new_tracking_setting_dict = {
            key: value for key, value in tracking_settings.__dict__.items() if key.startswith("_") is False
        }
        self.db.query(TrackingSettings).filter_by(rts_id=rts_id).update(new_tracking_setting_dict)
        self.db.commit()
        logger.info("Updated tracking settings for RTS with id: %s", rts_id)
        return self.get_tracking_settings(rts_id)
