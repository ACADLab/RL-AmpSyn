* Folded Cascode — PMOS input pair with NMOS mirror load
* DISTINCT from 5T_OTA: uses PMOS diff pair (wider input CM range)
* and current-source biased tail (not mirror) 
.PARAM w_in=10u l_in=20u w_load=10u l_load=20u w_tail=10u l_tail=20u w_cas=10u l_cas=20u ibias=0.1u

.include "/home/asus/Desktop/madcap26/rl_ampsyn/models/ptm180nm.lib"

.option reltol=1e-3 abstol=1e-12 itl1=500 itl2=500

Vdd vdd 0 1.8
Vss vss 0 0
Vic vic 0 0.9
Vid vid 0 dc 0 ac 1
E1 inp vic vid 0 0.5
E2 inn vic vid 0 -0.5

* PMOS tail current source (ideal current source for robust biasing)
Itail vdd stail {ibias}

* PMOS differential pair (note: wider W than 5T for lower flicker noise)
Min1 net1 inp stail vdd pmos W={w_in} L={l_in}
Min2 out inn stail vdd pmos W={w_in} L={l_in}

* NMOS active load (diode + mirror)
Mload1 net1 net1 vss vss nmos W={w_load} L={l_load}
Mload2 out net1 vss vss nmos W={w_load} L={l_load}

Cload out 0 10p

.control
op
ac dec 100 1 1G
meas ac gain_db MAX vdb(out)
meas ac gbw_hz WHEN vdb(out)=0 CROSS=1
meas ac pm_deg FIND vp(out) WHEN vdb(out)=0 CROSS=1
* Power = Ibias × VDD (since Itail is ideal source, Vdd current is only from loads)
let pwr_w = @Vdd[i] * 1.8
print gain_db gbw_hz pm_deg pwr_w
quit
.endc

.end