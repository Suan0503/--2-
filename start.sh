#!/bin/sh
flask db upgrade
exec gunicorn app:app -b 0.0.0.0:8080
