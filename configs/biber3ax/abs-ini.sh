#!/bin/sh
# Run by the #INCLUDE in biber3ax-abs.ini: writes biber3ax.ini (its #INCLUDEs expanded) to
# biber3ax-abs.ini.gen with HOME_ABSOLUTE_ENCODER = 2 and the [ABS_ENCODER] offset at the top of
# each [JOINT_n] (LinuxCNC 2.9 takes the first match, shadowing the switch homing values), no
# HOME_SEQUENCE (no Home All), plus abs-home.hal (homes each joint on the first Machine On).
# Prints the file name. "abs-ini.sh measure": print the offsets (LinuxCNC running, homed, at rest).
cd "$(dirname "$0")" || exit 1

# Error dialog, then stop the linuxcnc launcher — an empty #INCLUDE would start its INI update wizard.
fail() {
    echo "abs-ini.sh: $1" >&2
    [ -n "$DISPLAY" ] && printf 'wm withdraw .\ntk_messageBox -icon error -title biber3ax-abs.ini -message {%s}\nexit\n' "$1" |
        wish8.6 >/dev/null 2>&1
    # topmost "linuxcnc" ancestor = the launcher (its subshells have the same name)
    p=$$ top=
    while [ "$p" -gt 1 ]; do
        p=$(awk '{ print $4 }' /proc/$p/stat)
        [ "$(cat /proc/$p/comm)" = linuxcnc ] && top=$p
    done
    [ -n "$top" ] && kill $top
    exit 1
}

if [ "$1" = measure ]; then
    for n in 0 1 2 3; do
        awk -v n=$n -v fb="$(halcmd getp joint.$n.pos-fb)" -v m="$(halcmd getp joint.$n.motor-pos-fb)" \
            'BEGIN { printf "JOINT_%d_HOME_OFFSET = %.4f\n", n, fb - m }'
    done
    exit
fi

out=biber3ax-abs.ini.gen
missing=$(awk '
FNR == NR {
    if (/^\[/) s = $0
    else if (s == "[ABS_ENCODER]" && $1 ~ /^JOINT_[0-9]+_HOME_OFFSET$/ && $3 != "") off[$1] = $3
    next
}
/^#INCLUDE / { while ((getline l < $2) > 0) print l; close($2); next }
/^\[/ { sec = $0 }
sec ~ /^\[JOINT_/ && $1 == "HOME_SEQUENCE" { next }
{ print }
/^\[HAL\]/ { print "POSTGUI_HALFILE = abs-home.hal" }
/^\[JOINT_[0-9]+\]/ {
    k = $0; sub(/^\[/, "", k); sub(/\].*/, "_HOME_OFFSET", k)
    if (!(k in off)) print k > "/dev/stderr"
    print "HOME_ABSOLUTE_ENCODER = 2"
    print "HOME_OFFSET = " off[k]
}
' biber3ax-abs.ini biber3ax.ini 2>&1 >$out) || fail "generating $out failed: $missing"
[ -z "$missing" ] || fail "Not set in [ABS_ENCODER] of biber3ax-abs.ini:
$missing

Home with biber3ax.ini, then run ./abs-ini.sh measure."
echo $out
