* Telescopic Cascode OTA — NMOS cascode stacking for high Rout/gain
* DISTINCT from 5T_OTA: adds cascode transistors for higher output impedance
* Expected gain: 55-65 dB (vs 5T_OTA's 40 dB)
.PARAM w_in=10u l_in=2u w_load=10u l_load=2u w_tail=10u l_tail=2u w_cas=10u l_cas=2u ibias=5u

.include "/home/asus/Desktop/madcap26/rl_ampsyn/models/ptm180nm.lib"

.option reltol=1e-3 abstol=1e-12 itl1=500 itl2=500

Vdd vdd 0 1.8
Vss vss 0 0
Vic vic 0 0.9
Vid vid 0 dc 0 ac 1
E1 inp vic vid 0 0.5
E2 inn vic vid 0 -0.5

* Tail current mirror
Iref vdd nbias {ibias}
Mref nbias nbias vss vss nmos W={w_tail} L={l_tail}
Mtail tail nbias vss vss nmos W={w_tail} L={l_tail}

* NMOS diff pair
Min1 d1 inp tail vss nmos W={w_in} L={l_in}
Min2 d2 inn tail vss nmos W={w_in} L={l_in}

* NMOS cascode on top of diff pair (self-biased via diode on mirror side)
Mcas1 cas1 cas1 d1 vss nmos W={w_cas} L={l_cas}
Mcas2 out cas1 d2 vss nmos W={w_cas} L={l_cas}

* PMOS load: diode-connected + mirror (simple, no cascode on PMOS)
Mload1 cas1 cas1 vdd vdd pmos W={w_load} L={l_load}
Mload2 out cas1 vdd vdd pmos W={w_load} L={l_load}

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