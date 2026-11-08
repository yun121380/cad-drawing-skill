"""轴承座的全部设计尺寸（mm）。build.py 建模、views.py 出视图、drawing.py 标注都从这里取，
改这里的数再把三个脚本依次重跑，图上的线和尺寸位置都会跟着变（标注坐标不再手抄）。
坐标约定：轴孔轴线沿 Z、位于 (X=0, Y=AXIS_H)；底面 Y=0；前后对称 Z=±L/2，左右对称 X=0。"""
BASE_L, BASE_H = 160, 16          # 底座长、厚
L = 60                            # 底座宽 = 圆筒长（Z 向）
RECESS_W, RECESS_H = 90, 3        # 底面凹槽
AXIS_H = 70                       # 中心高
BOSS_D = 90                       # 圆筒外径
BORE_D = 52                       # 轴孔 Φ52H7
BORE_TOL = ("+0.030", "0")
CH = 1.5                          # 轴孔两端倒角
SEAL_D, SEAL_W, SEAL_E = 60, 5, 5  # 密封槽直径、宽、离端面距离
OILG_D, OILG_W = 56, 8            # 中间油槽
WEB_T, WEB_FOOT = 20, 100         # 支承板厚、底部宽（上端与圆筒相切）
OIL_D, OIL_TOP = 20, 122          # 油杯凸台直径、顶面高
TAP_D, THREAD, THREAD_L = 8.5, ("M10-7H", 10), 14   # 底孔、螺纹、螺纹深
HOLE_D, CB_D, CB_H, HOLE_X = 13, 22, 2, 64          # 安装孔、锪平、锪平深、孔中心 X
FIL = 3                           # 铸造圆角

H_TOTAL = OIL_TOP                 # 外框高
