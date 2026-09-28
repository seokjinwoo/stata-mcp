"""Configuration without importing or starting Stata."""
from dataclasses import dataclass
import math
import os
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    stata_home: Path
    edition: str
    workdir: Path
    timeout: float = 120.0
    startup_timeout: float = 60.0

    def __post_init__(self):
        object.__setattr__(self, 'stata_home', Path(self.stata_home).expanduser().resolve())
        object.__setattr__(self, 'workdir', Path(self.workdir).expanduser().resolve())
        if self.edition not in ('be', 'se', 'mp'):
            raise ValueError('STATA_EDITION must be be, se, or mp')
        if not (self.stata_home / 'utilities' / 'pystata').is_dir():
            raise ValueError('STATA_HOME must contain utilities/pystata')
        for value in (self.timeout, self.startup_timeout):
            if not math.isfinite(value) or value <= 0:
                raise ValueError('Timeout must be finite and positive')
        if any(c in str(self.workdir) for c in ('"', '\n', '\r', '`', '$')):
            raise ValueError('Working directory contains unsupported Stata macro/quote characters')

    @classmethod
    def from_env(cls):
        home = os.environ.get('STATA_HOME')
        if not home:
            raise ValueError('Set STATA_HOME to your licensed Stata installation directory')
        return cls(Path(home), os.environ.get('STATA_EDITION', 'be').lower(),
                   Path(os.environ.get('STATA_WORKDIR', './stata-work')),
                   float(os.environ.get('STATA_TIMEOUT', '120')),
                   float(os.environ.get('STATA_STARTUP_TIMEOUT', '60')))
