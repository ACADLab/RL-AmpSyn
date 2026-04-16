* Recycling Folded Cascode (RFC) — PMOS input with cascoded NMOS load
* DISTINCT from Folded_Cascode: adds cascode layer on NMOS load for higher gain
* Expected: ~50-60dB (vs FC's ~37dB)
.PARAM w_in=10u l_in=5u w_load=10u l_load=5u w_tail=10u l_tail=5u w_cas=10u l_cas=5u ibias=5u

.include "/home/asus/Desktop/madcap26/rl_ampsyn/models/ptm180nm.lib"

.option reltol=1e-3 abstol=1e-12 itl1=500 itl2=500

Vdd vdd 0 1.8
Vss vss 0 0
Vic vic 0 0.9
Vid vid 0 dc 0 ac 1
E1 inp vic vid 0 0.5
E2 inn vic vid 0 -0.5

* PMOS tail (ideal current source)
Itail vdd stail {ibias}

* PMOS differential pair
Min1 d1 inp stail vdd pmos W={w_in} L={l_in}
Min2 d2 inn stail vdd pmos W={w_in} L={l_in}

* NMOS load level 1 (mirror)
Mload1 d1 d1 vss vss nmos W={w_load} L={l_load}
Mload2 d2 d1 vss vss nmos W={w_load} L={l_load}

* NMOS cascode level 2 (self-biased via diode on mirror side)
Mcas1 cas1 cas1 d1 vss nmos W={w_cas} L={l_cas}
Mcas2 out cas1 d2 vss nmos W={w_cas} L={l_cas}

* PMOS cascode load (diode + mirror)
Mpcas1 cas1 cas1 vdd vdd pmos W={w_cas} L={l_cas}
Mpcas2 out cas1 vdd vdd pmos W={w_cas} L={l_cas}

Cload out 0 10p

.control
op
ac dec 100 1 1G
meas ac gain_db MAX vdb(out)
meas ac gbw_hz WHEN vdb(out)=0 CROSS=1
meas ac pm_deg FIND vp(out) WHEN vdb(out)=0 CROSS=1
let pwr_w = @Vdd[i] * 1.8
print gain_db gbw_hz pm_deg pwr_w
quit
.endc

.end