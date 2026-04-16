* Current Feedback Amplifier (CFA) — Complementary input + transimpedance
* DISTINCT from 5T_OTA: uses complementary NMOS+PMOS input pairs
* and a transimpedance output stage for higher bandwidth
.PARAM w_in=10u l_in=10u w_load=10u l_load=10u w_tail=10u l_tail=10u ibias=1u

.include "/home/asus/Desktop/madcap26/rl_ampsyn/models/ptm180nm.lib"

.option reltol=1e-3 abstol=1e-12 itl1=500 itl2=500

Vdd vdd 0 1.8
Vss vss 0 0
Vic vic 0 0.9
Vid vid 0 dc 0 ac 1
E1 inp vic vid 0 0.5
E2 inn vic vid 0 -0.5

* NMOS tail + diff pair (bottom half)
Irefn vdd nbiasn {ibias}
Mrefn nbiasn nbiasn vss vss nmos W={w_tail} L={l_tail}
Mtailn tailn nbiasn vss vss nmos W={w_tail} L={l_tail}
Mn1 netn1 inp tailn vss nmos W={w_in} L={l_in}
Mn2 outn inn tailn vss nmos W={w_in} L={l_in}

* PMOS tail + diff pair (top half — complementary)
Irefp vss nbiasp {ibias}
Mrefp nbiasp nbiasp vdd vdd pmos W={w_tail} L={l_tail}
Mtailp tailp nbiasp vdd vdd pmos W={w_tail} L={l_tail}
Mp1 netp1 inp tailp vdd pmos W={w_in} L={l_in}
Mp2 outp inn tailp vdd pmos W={w_in} L={l_in}

* Fold NMOS outputs into PMOS loads and vice versa
Mln1 netn1 netn1 vdd vdd pmos W={w_load} L={l_load}
Mln2 outn netn1 vdd vdd pmos W={w_load} L={l_load}
Mlp1 netp1 netp1 vss vss nmos W={w_load} L={l_load}
Mlp2 outp netp1 vss vss nmos W={w_load} L={l_load}

* Sum the two complementary outputs through resistors
Rn outn out 10k
Rp outp out 10k

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