* Two-Stage Miller Compensated Op-Amp  
.PARAM w_in=2u l_in=500n w_load=4u l_load=500n w_tail=4u l_tail=500n w_2=8u l_2=500n ibias=10u cc=1p

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

* Stage 2: PMOS CS (gate driven by stg1, drain is output)
* Using a current source load instead of self-biased mirror
Ibias2 out vss {ibias}
M2 out stg1 vdd vdd pmos W={w_2} L={l_2}

* Miller compensation
Cc stg1 out {cc}

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