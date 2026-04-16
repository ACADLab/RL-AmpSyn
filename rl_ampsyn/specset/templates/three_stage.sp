* Three-Stage Op-Amp with Nested Miller Compensation
.PARAM w_in=16u l_in=550n w_load=16u l_load=550n w_tail=16u l_tail=550n w_2=32u l_2=250n w_3=64u l_3=250n ibias=5u cc1=1p cc2=500f

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

* Stage 1: Diff pair + active load
Min1 net1 inp tail vss nmos W={w_in} L={l_in}
Min2 stg1 inn tail vss nmos W={w_in} L={l_in}
Mload1 net1 net1 vdd vdd pmos W={w_load} L={l_load}
Mload2 stg1 net1 vdd vdd pmos W={w_load} L={l_load}

* Stage 2: PMOS CS with current source load
Ibias2 stg2 vss {ibias}
M2 stg2 stg1 vdd vdd pmos W={w_2} L={l_2}

* Stage 3: PMOS CS with current source load
Ibias3 out vss {ibias}
M3 out stg2 vdd vdd pmos W={w_3} L={l_3}

* Nested Miller compensation
Cc1 stg1 out {cc1}
Cc2 stg2 out {cc2}

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