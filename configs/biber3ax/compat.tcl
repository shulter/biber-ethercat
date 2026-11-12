# LinuxCNC 2.9 vs 2.10, after ethercat.hal: components 2.10 renamed (same pins, used in io.hal/postgui.hal),
# and 2.10's initf for the lcec master activation (else lcec warns and activates inline, as on 2.9).
if {[string match 2.9.* $::env(LINUXCNCVERSION)]} {
    set conv_bit_float conv_bit_float; set conv_s32_float conv_s32_float; set scaled_sums scaled_s32_sums
} else {
    set conv_bit_float conv_bool_real; set conv_s32_float conv_sint_real; set scaled_sums scaled_sint_sums
    hal initf lcec.activate servo-thread
}
loadrt $conv_bit_float names=x-moving-float
loadrt $conv_s32_float names=x-left-vel-conv,x-right-vel-conv,y-vel-conv,z-vel-conv
loadrt $scaled_sums    names=pendant-jog-speed
