#!/bin/bash

cd /var/www/autograders
python3 grader.py
chgrp -R instructors .work ../html/*/.htresults 2>/dev/null
chmod -R g+w .work ../html/*/.htresults 2>/dev/null
