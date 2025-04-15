from fastapi import Depends
from sqlalchemy.orm import Session

from rtsapi.database.models import RTS
from rtsapi.dependencies import get_db
from rtsapi.exceptions import RTSNotFoundException, RTSPortAlreadyExistsException


class RTSRepository:

    def __init__(self, db: Session = Depends(get_db)):
        self.db = db

    def create_rts(self, rts: RTS) -> RTS:
        same_port_rts = (
            self.db.query(RTS)
            .filter(RTS.port == rts.port, RTS.device_id == rts.device_id, RTS.deleted == False)
            .first()
        )

        if same_port_rts:
            raise RTSPortAlreadyExistsException(rts.port)

        self.db.add(rts)
        self.db.commit()
        self.db.refresh(rts)
        return rts

    def get_rts(self, rts_id: int) -> RTS:
        db_rts = self.db.query(RTS).filter(RTS.id == rts_id, RTS.deleted == False).first()

        if db_rts is None:
            raise RTSNotFoundException(rts_id)

        return db_rts

    def get_all_rts(self) -> list[RTS]:
        return self.db.query(RTS).filter(RTS.deleted == False).all()

    def update_rts(self, rts_id: int, rts: RTS) -> RTS:
        self.db.query(RTS).filter(RTS.id == rts_id, RTS.deleted == False).update(rts.__dict__)
        self.db.commit()
        updated_rts = self.db.query(RTS).filter(RTS.id == rts_id).first()
        return updated_rts

    def delete_rts(self, rts_id: int) -> None:
        rts = self.db.query(RTS).filter_by(id=rts_id).first()

        if rts is None:
            raise RTSNotFoundException(rts_id)

        rts.deleted = True
        self.db.commit()

    def add_to_external_delay(self, rts_id: int, delay: float) -> None:
        self.db.query(RTS).filter(RTS.id == rts_id).update({RTS.external_delay: RTS.external_delay + delay})
        self.db.commit()

    def update_internal_delay(self, rts_id: int, internal_delay: float) -> None:
        self.db.query(RTS).filter(RTS.id == rts_id).update({RTS.internal_delay: internal_delay})
        self.db.commit()

    def get_station(self, rts_id: int) -> dict:
        return (
            self.db.query(RTS.station_x, RTS.station_y, RTS.station_z, RTS.orientation)
            .filter(RTS.id == rts_id)
            .first()
            ._asdict()
        )

    def set_station(
        self, rts_id: int, station_x: float, station_y: float, station_z: float, orientation: float
    ) -> None:
        self.db.query(RTS).filter(RTS.id == rts_id).update(
            {
                RTS.station_x: station_x,
                RTS.station_y: station_y,
                RTS.station_z: station_z,
                RTS.orientation: orientation,
            }
        )
        self.db.commit()

    def move_station(
        self, rts_id: int, station_x: float, station_y: float, station_z: float, orientation: float
    ) -> None:
        self.db.query(RTS).filter(RTS.id == rts_id).update(
            {
                RTS.station_x: RTS.station_x + station_x,
                RTS.station_y: RTS.station_y + station_y,
                RTS.station_z: RTS.station_z + station_z,
                RTS.orientation: RTS.orientation - orientation,
            }
        )
        self.db.commit()
