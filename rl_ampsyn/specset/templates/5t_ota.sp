* 5-Transistor OTA (Simple Differential Pair)
.PARAM w_in=10u l_in=5u w_load=10u l_load=5u w_tail=10u l_tail=5u ibias=1u

.include "/home/asus/Desktop/madcap26/rl_ampsyn/models/ptm180nm.lib"

.option reltol=1e-3 abstol=1e-12 itl1=500 itl2=500

Vdd vdd 0 1.8
Vss vss 0 0
Vic vic 0 0.9
Vid vid 0 dc 0 ac 1
E1 inp vic vid 0 0.5
E2 inn vic vid 0 -0.5

Iref vdd nbias {ibias}
Mref nbias nbias vss vss nmos W={w_tail} L={l_tail}
Mtail tail nbias vss vss nmos W={w_tail} L={l_tail}

Min1 net1 inp tail vss nmos W={w_in} L={l_in}
Min2 out inn tail vss nmos W={w_in} L={l_in}

Mload1 net1 net1 vdd vdd pmos W={w_load} L={l_load}
Mload2 out net1 vdd vdd pmos W={w_load} L={l_load}

Cload out 0 10p

.control
op
ac dec 100 1 1G
meas ac gain_db MAX vdb(out)
meas ac gbw_hz WHEN vdb(out)=0 CROSS=1
meas ac pm_deg FIND vp(out) WHEN vdb(out)=0 CROSS=1
meas dc pwr AVG i(Vdd)
let pwr_w = @Vdd[i] * 1.8
print gain_db gbw_hz pm_deg pwr_w
quit
.endc

.end