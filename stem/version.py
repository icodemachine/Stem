"""
Tor versioning information and requirements for its features. These can be
easily parsed and compared, for instance...

::

  >>> my_version = stem.version.get_system_tor_version()
  >>> print my_version
  0.2.1.30
  >>> my_version.meets_requirements(stem.version.Requirement.CONTROL_SOCKET)
  True

**Module Overview:**

::

  get_system_tor_version - gets the version of our system's tor installation
  
  Version - Tor versioning information.
    |- meets_requirements - checks if this version meets the given requirements
    |- __str__ - string representation
    +- __cmp__ - compares with another Version
  
  VersionRequirements - Series of version requirements
    |- greater_than - adds rule that matches if we're greater than a version
    |- less_than    - adds rule that matches if we're less than a version
    +- in_range     - adds rule that matches if we're within a given version range
  
  Requirement - Enumerations for the version requirements of features.
    |- AUTH_SAFECOOKIE      - 'SAFECOOKIE' authentication method
    |- GETINFO_CONFIG_TEXT  - 'GETINFO config-text' query
    |- TORRC_CONTROL_SOCKET - 'ControlSocket <path>' config option
    +- TORRC_DISABLE_DEBUGGER_ATTACHMENT - 'DisableDebuggerAttachment' config option
"""

import re

import stem.util.enum
import stem.util.system

# cache for the get_system_tor_version function
VERSION_CACHE = {}

def get_system_tor_version(tor_cmd = "tor"):
  """
  Queries tor for its version. This is os dependent, only working on linux,
  osx, and bsd.
  
  :param str tor_cmd: command used to run tor
  
  :returns: :class:`stem.version.Version` provided by the tor command
  
  :raises: IOError if unable to query or parse the version
  """
  
  if not tor_cmd in VERSION_CACHE:
    try:
      version_cmd = "%s --version" % tor_cmd
      version_output = stem.util.system.call(version_cmd)
    except OSError, exc:
      raise IOError(exc)
    
    if version_output:
      # output example:
      # Oct 21 07:19:27.438 [notice] Tor v0.2.1.30. This is experimental software. Do not rely on it for strong anonymity. (Running on Linux i686)
      # Tor version 0.2.1.30.
      
      last_line = version_output[-1]
      
      if last_line.startswith("Tor version ") and last_line.endswith("."):
        try:
          version_str = last_line[12:last_line.find(' ', 12)]
          VERSION_CACHE[tor_cmd] = Version(version_str)
        except ValueError, exc:
          raise IOError(exc)
      else:
        raise IOError("Unexpected response from '%s': %s" % (version_cmd, last_line))
    else:
      raise IOError("'%s' didn't have any output" % version_cmd)
  
  return VERSION_CACHE[tor_cmd]

class Version:
  """
  Comparable tor version. These are constructed from strings that conform to
  the 'new' style in the `tor version-spec
  <https://gitweb.torproject.org/torspec.git/blob/HEAD:/version-spec.txt>`_,
  such as "0.1.4" or "0.2.2.23-alpha (git-7dcd105be34a4f44)".
  
  :var int major: major version
  :var int minor: minor version
  :var int micro: micro version
  :var int patch: optional patch level (None if undefined)
  :var str status: optional status tag without the preceding dash such as 'alpha', 'beta-dev', etc (None if undefined)
  
  :param str version_str: version to be parsed
  
  :raises: ValueError if input isn't a valid tor version
  """
  
  def __init__(self, version_str):
    self.version_str = version_str
    version_parts = re.match(r'^([0-9]+)\.([0-9]+)\.([0-9]+)(\.[0-9]+)?(-\S*)?$', version_str)
    
    if version_parts:
      major, minor, micro, patch, status = version_parts.groups()
      
      # The patch and status matches are optional (may be None) and have an extra
      # proceeding period or dash if they exist. Stripping those off.
      
      if patch: patch = int(patch[1:])
      if status: status = status[1:]
      
      self.major = int(major)
      self.minor = int(minor)
      self.micro = int(micro)
      self.patch = patch
      self.status = status
    else: raise ValueError("'%s' isn't a properly formatted tor version" % version_str)
  
  def meets_requirements(self, requirements):
    """
    Checks if this version meets the requirements for a given feature.
    
    Requirements can be either a :class:`stem.version.Version` or
    :class:`stem.version.VersionRequirements`.
    
    :param requirements: requrirements to be checked for
    """
    
    if isinstance(requirements, Version):
      return self >= requirements
    else:
      for rule in requirements.rules:
        if rule(self): return True
      
      return False
  
  def __str__(self):
    """
    Provides the string used to construct the Version.
    """
    
    return self.version_str
  
  def __cmp__(self, other):
    """
    Simple comparison of versions. An undefined patch level is treated as zero
    and status tags are not included in comparisions (as per the version spec).
    """
    
    if not isinstance(other, Version):
      return 1 # this is also used for equality checks
    
    for attr in ("major", "minor", "micro", "patch"):
      my_version = max(0, self.__dict__[attr])
      other_version = max(0, other.__dict__[attr])
      
      if my_version > other_version: return 1
      elif my_version < other_version: return -1
    
    my_status = self.status if self.status else ""
    other_status = other.status if other.status else ""
    
    # not including tags in comparisons because the spec declares them to be
    # 'purely informational'
    return 0

class VersionRequirements:
  """
  Series of version constraints that can be compared to. For instance, it
  allows for comparisons like 'if I'm greater than version X in the 0.2.2
  series, or greater than version Y in the 0.2.3 series'.
  
  This is a logical 'or' of the series of rules.
  """
  
  def __init__(self, rule = None):
    self.rules = []
    
    if rule: self.greater_than(rule)
  
  def greater_than(self, version, inclusive = True):
    """
    Adds a constraint that we're greater than the given version.
    
    :param stem.version.Version verison: version we're checking against
    :param bool inclusive: if comparison is inclusive or not
    """
    
    if inclusive:
      self.rules.append(lambda v: version <= v)
    else:
      self.rules.append(lambda v: version < v)
  
  def less_than(self, version, inclusive = True):
    """
    Adds a constraint that we're less than the given version.
    
    :param stem.version.Version verison: version we're checking against
    :param bool inclusive: if comparison is inclusive or not
    """
    
    if inclusive:
      self.rules.append(lambda v: version >= v)
    else:
      self.rules.append(lambda v: version > v)
  
  def in_range(self, from_version, to_version, from_inclusive = True, to_inclusive = False):
    """
    Adds constraint that we're within the range from one version to another.
    
    :param stem.version.Version from_verison: beginning of the comparison range
    :param stem.version.Version to_verison: end of the comparison range
    :param bool from_inclusive: if comparison is inclusive with the starting version
    :param bool to_inclusive: if comparison is inclusive with the ending version
    """
    
    if from_inclusive and to_inclusive:
      new_rule = lambda v: from_version <= v <= to_version
    elif from_inclusive:
      new_rule = lambda v: from_version <= v < to_version
    else:
      new_rule = lambda v: from_version < v < to_version
    
    self.rules.append(new_rule)

safecookie_req = VersionRequirements()
safecookie_req.in_range(Version("0.2.2.36"), Version("0.2.3.0"))
safecookie_req.greater_than(Version("0.2.3.13"))

Requirement = stem.util.enum.Enum(
  ("AUTH_SAFECOOKIE", safecookie_req),
  ("GETINFO_CONFIG_TEXT", Version("0.2.2.7")),
  ("LOADCONF", Version("0.2.1.1")),
  ("TORRC_CONTROL_SOCKET", Version("0.2.0.30")),
  ("TORRC_DISABLE_DEBUGGER_ATTACHMENT", Version("0.2.3.9")),
)

