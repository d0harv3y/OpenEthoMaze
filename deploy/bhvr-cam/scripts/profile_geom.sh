#!/bin/bash
# Profile geometry for bhvr-cam (sourced by record helpers).
profile_geom() {
  case "${1:-720p30}" in
    720p30) echo "1280 720 30" ;;
    720p20) echo "1280 720 20" ;;
    480p30) echo "640 480 30" ;;
    *) return 1 ;;
  esac
}
