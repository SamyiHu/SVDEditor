# H ↔ SVD 覆盖率报告

- 模式：header_vs_svd
- H 外设数：44 / SVD 外设数：37 / 匹配：36
- 寄存器：匹配 155 / H 总数 200
- 位域：匹配 540 / H 总数 712
- header_coverage_percent：77.5%
- trm_supplement_percent：67.0%
- 未解析 H 条目：28

## H 有、SVD 无的外设
- RCC（7 个寄存器，0x4000300C）
- FPGA（1 个寄存器，0x40022140）
- TK（5 个寄存器，0x40022200）
- EXTI（8 个寄存器，0x40011300）
- GPIOA_BIT（2 个寄存器，0x40011000）
- GPIOB_BIT（2 个寄存器，0x40011000）
- GPIOC_BIT（2 个寄存器，0x40011000）
- OPT（2 个寄存器，0x400003F8）

## SVD 有、H 无的外设
- INT（8 个寄存器）
- LEDPWM（34 个寄存器）

## 差异统计
- base_address_mismatch: 3
- field_missing_in_header: 48
- field_missing_in_svd: 25
- field_name_diff: 69
- peripheral_missing_in_header: 2
- peripheral_missing_in_svd: 8
- peripheral_name_diff: 5
- register_missing_in_header: 37
- register_missing_in_svd: 16
- register_name_diff: 145

## 差异明细（前 200 条）
| 类型 | 外设 | 寄存器 | 位域 | 说明 | H 行号 |
| --- | --- | --- | --- | --- | --- |
| peripheral_missing_in_svd | RCC |  |  | SVD 缺少外设 RCC（H 基地址 0x4000300C） | 612 |
| peripheral_name_diff | RCCAHB |  |  | 外设名不同：H=RCCAHB SVD=RCC_AHB | - |
| field_name_diff | RCCAHB | AHB_CFG | IFBCFG | 位域名不同：H=IFBCFG SVD=IFBEN（bit 2） | - |
| register_missing_in_header | RCC_AHB | RCC_KEY |  | H 文件未见寄存器 RCC_AHB/RCC_KEY（仅 SVD 存在，offset=0x0C） | - |
| register_missing_in_header | RCC_AHB | RCC_CFG0 |  | H 文件未见寄存器 RCC_AHB/RCC_CFG0（仅 SVD 存在，offset=0x14） | - |
| register_missing_in_header | RCC_AHB | RCC_CFG1 |  | H 文件未见寄存器 RCC_AHB/RCC_CFG1（仅 SVD 存在，offset=0x18） | - |
| register_missing_in_header | RCC_AHB | PLL_CFG |  | H 文件未见寄存器 RCC_AHB/PLL_CFG（仅 SVD 存在，offset=0x1C） | - |
| register_missing_in_header | RCC_AHB | RCC_STS |  | H 文件未见寄存器 RCC_AHB/RCC_STS（仅 SVD 存在，offset=0x20） | - |
| register_missing_in_header | RCC_AHB | SYST_CALIB |  | H 文件未见寄存器 RCC_AHB/SYST_CALIB（仅 SVD 存在，offset=0x28） | - |
| register_missing_in_header | RCC_AHB | NMI_CFG |  | H 文件未见寄存器 RCC_AHB/NMI_CFG（仅 SVD 存在，offset=0x2C） | - |
| peripheral_name_diff | RCCAPB0 |  |  | 外设名不同：H=RCCAPB0 SVD=RCC_APB0 | - |
| field_missing_in_svd | RCCAPB0 | APB0_CFG | RDMODE | SVD 缺少位域 RCCAPB0/APB0_CFG/RDMODE（H bit[31:31]） | 979 |
| peripheral_name_diff | RCCAPB1 |  |  | 外设名不同：H=RCCAPB1 SVD=RCC_APB0 | - |
| register_name_diff | RCCAPB1 | APB1_CFG |  | 寄存器名不同：H=APB1_CFG SVD=APB0_CFG | - |
| field_name_diff | RCCAPB1 | APB1_CFG | TIM4EN | 位域名不同：H=TIM4EN SVD=TIM0EN（bit 0） | - |
| field_name_diff | RCCAPB1 | APB1_CFG | TIM5EN | 位域名不同：H=TIM5EN SVD=TIM1EN（bit 1） | - |
| field_name_diff | RCCAPB1 | APB1_CFG | TIM6EN | 位域名不同：H=TIM6EN SVD=TIM2EN（bit 2） | - |
| field_name_diff | RCCAPB1 | APB1_CFG | TIM7EN | 位域名不同：H=TIM7EN SVD=TIM3EN（bit 3） | - |
| field_name_diff | RCCAPB1 | APB1_CFG | TWI1EN | 位域名不同：H=TWI1EN SVD=TWI0EN（bit 4） | - |
| field_name_diff | RCCAPB1 | APB1_CFG | UART2EN | 位域名不同：H=UART2EN SVD=UART1EN（bit 7） | - |
| field_missing_in_svd | RCCAPB1 | APB1_CFG | RDMODE | SVD 缺少位域 RCCAPB1/APB1_CFG/RDMODE（H bit[31:31]） | 983 |
| field_missing_in_header | RCC_APB0 | APB0_CFG | SPI0EN | H 文件未见位域 RCC_APB0/APB0_CFG/SPI0EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | UART0EN | H 文件未见位域 RCC_APB0/APB0_CFG/UART0EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | PWM0EN | H 文件未见位域 RCC_APB0/APB0_CFG/PWM0EN（仅 SVD 存在） | - |
| register_name_diff | RCCAPB1 | APB1_RST |  | 寄存器名不同：H=APB1_RST SVD=APB0_RST | - |
| field_name_diff | RCCAPB1 | APB1_RST | TIM4EN | 位域名不同：H=TIM4EN SVD=TIM0RST（bit 0） | - |
| field_name_diff | RCCAPB1 | APB1_RST | TIM5EN | 位域名不同：H=TIM5EN SVD=TIM1RST（bit 1） | - |
| field_name_diff | RCCAPB1 | APB1_RST | TIM6EN | 位域名不同：H=TIM6EN SVD=TIM2RST（bit 2） | - |
| field_name_diff | RCCAPB1 | APB1_RST | TIM7EN | 位域名不同：H=TIM7EN SVD=TIM3RST（bit 3） | - |
| field_name_diff | RCCAPB1 | APB1_RST | TWI1EN | 位域名不同：H=TWI1EN SVD=TWI0RST（bit 4） | - |
| field_name_diff | RCCAPB1 | APB1_RST | UART2EN | 位域名不同：H=UART2EN SVD=UART1RST（bit 7） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | SPI0RST | H 文件未见位域 RCC_APB0/APB0_RST/SPI0RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | UART0RST | H 文件未见位域 RCC_APB0/APB0_RST/UART0RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | PWM0RST | H 文件未见位域 RCC_APB0/APB0_RST/PWM0RST（仅 SVD 存在） | - |
| peripheral_name_diff | RCCAPB2 |  |  | 外设名不同：H=RCCAPB2 SVD=RCC_APB0 | - |
| register_name_diff | RCCAPB2 | APB2_CFG |  | 寄存器名不同：H=APB2_CFG SVD=APB0_CFG | - |
| field_name_diff | RCCAPB2 | APB2_CFG | PWM1EN | 位域名不同：H=PWM1EN SVD=TIM0EN（bit 0） | - |
| field_name_diff | RCCAPB2 | APB2_CFG | LCDEN | 位域名不同：H=LCDEN SVD=TIM1EN（bit 1） | - |
| field_name_diff | RCCAPB2 | APB2_CFG | UART3EN | 位域名不同：H=UART3EN SVD=TIM2EN（bit 2） | - |
| field_missing_in_svd | RCCAPB2 | APB2_CFG | RDMODE | SVD 缺少位域 RCCAPB2/APB2_CFG/RDMODE（H bit[31:31]） | 987 |
| field_missing_in_header | RCC_APB0 | APB0_CFG | TIM3EN | H 文件未见位域 RCC_APB0/APB0_CFG/TIM3EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | TWI0EN | H 文件未见位域 RCC_APB0/APB0_CFG/TWI0EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | SPI0EN | H 文件未见位域 RCC_APB0/APB0_CFG/SPI0EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | UART0EN | H 文件未见位域 RCC_APB0/APB0_CFG/UART0EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | UART1EN | H 文件未见位域 RCC_APB0/APB0_CFG/UART1EN（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_CFG | PWM0EN | H 文件未见位域 RCC_APB0/APB0_CFG/PWM0EN（仅 SVD 存在） | - |
| register_name_diff | RCCAPB2 | APB2_RST |  | 寄存器名不同：H=APB2_RST SVD=APB0_RST | - |
| field_name_diff | RCCAPB2 | APB2_RST | PWM1RST | 位域名不同：H=PWM1RST SVD=TIM0RST（bit 0） | - |
| field_name_diff | RCCAPB2 | APB2_RST | LCDRST | 位域名不同：H=LCDRST SVD=TIM1RST（bit 1） | - |
| field_name_diff | RCCAPB2 | APB2_RST | UART3RST | 位域名不同：H=UART3RST SVD=TIM2RST（bit 2） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | TIM3RST | H 文件未见位域 RCC_APB0/APB0_RST/TIM3RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | TWI0RST | H 文件未见位域 RCC_APB0/APB0_RST/TWI0RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | SPI0RST | H 文件未见位域 RCC_APB0/APB0_RST/SPI0RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | UART0RST | H 文件未见位域 RCC_APB0/APB0_RST/UART0RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | UART1RST | H 文件未见位域 RCC_APB0/APB0_RST/UART1RST（仅 SVD 存在） | - |
| field_missing_in_header | RCC_APB0 | APB0_RST | PWM0RST | H 文件未见位域 RCC_APB0/APB0_RST/PWM0RST（仅 SVD 存在） | - |
| register_name_diff | UART0 | UART_CON |  | 寄存器名不同：H=UART_CON SVD=CON | - |
| field_missing_in_svd | UART0 | UART_CON | SM01 | SVD 缺少位域 UART0/UART_CON/SM01（H bit[0:1]） | 2380 |
| field_missing_in_svd | UART0 | UART_CON | BTKR | SVD 缺少位域 UART0/UART_CON/BTKR（H bit[3:3]） | 2388 |
| field_name_diff | UART0 | UART_CON | PERSCALER | 位域名不同：H=PERSCALER SVD=PRESCALER（bit 4） | - |
| field_missing_in_svd | UART0 | UART_CON | LBDL | SVD 缺少位域 UART0/UART_CON/LBDL（H bit[11:11]） | 2405 |
| field_missing_in_header | UART0 | CON | SM1 | H 文件未见位域 UART0/CON/SM1（仅 SVD 存在） | - |
| field_missing_in_header | UART0 | CON | SM0 | H 文件未见位域 UART0/CON/SM0（仅 SVD 存在） | - |
| register_name_diff | UART0 | UART_STS |  | 寄存器名不同：H=UART_STS SVD=STS | - |
| field_missing_in_svd | UART0 | UART_STS | BKIE | SVD 缺少位域 UART0/UART_STS/BKIE（H bit[3:3]） | 2422 |
| register_name_diff | UART0 | UART_BAUD |  | 寄存器名不同：H=UART_BAUD SVD=BAUD | - |
| register_name_diff | UART0 | UART_DATA |  | 寄存器名不同：H=UART_DATA SVD=DATA | - |
| register_name_diff | UART0 | UART_IDE |  | 寄存器名不同：H=UART_IDE SVD=IDE | - |
| field_missing_in_svd | UART0 | UART_IDE | BKIE | SVD 缺少位域 UART0/UART_IDE/BKIE（H bit[3:3]） | 2442 |
| field_missing_in_header | UART0 | IDE | RXIE | H 文件未见位域 UART0/IDE/RXIE（仅 SVD 存在） | - |
| register_name_diff | UART1 | UART_CON |  | 寄存器名不同：H=UART_CON SVD=CON | - |
| field_missing_in_svd | UART1 | UART_CON | SM01 | SVD 缺少位域 UART1/UART_CON/SM01（H bit[0:1]） | 2380 |
| field_missing_in_svd | UART1 | UART_CON | BTKR | SVD 缺少位域 UART1/UART_CON/BTKR（H bit[3:3]） | 2388 |
| field_name_diff | UART1 | UART_CON | PERSCALER | 位域名不同：H=PERSCALER SVD=PRESCALER（bit 4） | - |
| field_missing_in_svd | UART1 | UART_CON | LBDL | SVD 缺少位域 UART1/UART_CON/LBDL（H bit[11:11]） | 2405 |
| field_missing_in_header | UART1 | CON | SM1 | H 文件未见位域 UART1/CON/SM1（仅 SVD 存在） | - |
| field_missing_in_header | UART1 | CON | SM0 | H 文件未见位域 UART1/CON/SM0（仅 SVD 存在） | - |
| register_name_diff | UART1 | UART_STS |  | 寄存器名不同：H=UART_STS SVD=STS | - |
| field_missing_in_svd | UART1 | UART_STS | BKIE | SVD 缺少位域 UART1/UART_STS/BKIE（H bit[3:3]） | 2422 |
| register_name_diff | UART1 | UART_BAUD |  | 寄存器名不同：H=UART_BAUD SVD=BAUD | - |
| register_name_diff | UART1 | UART_DATA |  | 寄存器名不同：H=UART_DATA SVD=DATA | - |
| register_name_diff | UART1 | UART_IDE |  | 寄存器名不同：H=UART_IDE SVD=IDE | - |
| field_missing_in_svd | UART1 | UART_IDE | BKIE | SVD 缺少位域 UART1/UART_IDE/BKIE（H bit[3:3]） | 2442 |
| field_missing_in_header | UART1 | IDE | RXIE | H 文件未见位域 UART1/IDE/RXIE（仅 SVD 存在） | - |
| register_name_diff | UART2 | UART_CON |  | 寄存器名不同：H=UART_CON SVD=CON | - |
| field_missing_in_svd | UART2 | UART_CON | SM01 | SVD 缺少位域 UART2/UART_CON/SM01（H bit[0:1]） | 2380 |
| field_missing_in_svd | UART2 | UART_CON | BTKR | SVD 缺少位域 UART2/UART_CON/BTKR（H bit[3:3]） | 2388 |
| field_name_diff | UART2 | UART_CON | PERSCALER | 位域名不同：H=PERSCALER SVD=PRESCALER（bit 4） | - |
| field_missing_in_svd | UART2 | UART_CON | LBDL | SVD 缺少位域 UART2/UART_CON/LBDL（H bit[11:11]） | 2405 |
| field_missing_in_header | UART2 | CON | SM1 | H 文件未见位域 UART2/CON/SM1（仅 SVD 存在） | - |
| field_missing_in_header | UART2 | CON | SM0 | H 文件未见位域 UART2/CON/SM0（仅 SVD 存在） | - |
| register_name_diff | UART2 | UART_STS |  | 寄存器名不同：H=UART_STS SVD=STS | - |
| field_missing_in_svd | UART2 | UART_STS | BKIE | SVD 缺少位域 UART2/UART_STS/BKIE（H bit[3:3]） | 2422 |
| register_name_diff | UART2 | UART_BAUD |  | 寄存器名不同：H=UART_BAUD SVD=BAUD | - |
| register_name_diff | UART2 | UART_DATA |  | 寄存器名不同：H=UART_DATA SVD=DATA | - |
| register_name_diff | UART2 | UART_IDE |  | 寄存器名不同：H=UART_IDE SVD=IDE | - |
| field_missing_in_svd | UART2 | UART_IDE | BKIE | SVD 缺少位域 UART2/UART_IDE/BKIE（H bit[3:3]） | 2442 |
| field_missing_in_header | UART2 | IDE | RXIE | H 文件未见位域 UART2/IDE/RXIE（仅 SVD 存在） | - |
| register_name_diff | UART3 | UART_CON |  | 寄存器名不同：H=UART_CON SVD=CON | - |
| field_missing_in_svd | UART3 | UART_CON | SM01 | SVD 缺少位域 UART3/UART_CON/SM01（H bit[0:1]） | 2380 |
| field_missing_in_svd | UART3 | UART_CON | BTKR | SVD 缺少位域 UART3/UART_CON/BTKR（H bit[3:3]） | 2388 |
| field_name_diff | UART3 | UART_CON | PERSCALER | 位域名不同：H=PERSCALER SVD=PRESCALER（bit 4） | - |
| field_missing_in_svd | UART3 | UART_CON | LBDL | SVD 缺少位域 UART3/UART_CON/LBDL（H bit[11:11]） | 2405 |
| field_missing_in_header | UART3 | CON | SM1 | H 文件未见位域 UART3/CON/SM1（仅 SVD 存在） | - |
| field_missing_in_header | UART3 | CON | SM0 | H 文件未见位域 UART3/CON/SM0（仅 SVD 存在） | - |
| register_name_diff | UART3 | UART_STS |  | 寄存器名不同：H=UART_STS SVD=STS | - |
| field_missing_in_svd | UART3 | UART_STS | BKIE | SVD 缺少位域 UART3/UART_STS/BKIE（H bit[3:3]） | 2422 |
| register_name_diff | UART3 | UART_BAUD |  | 寄存器名不同：H=UART_BAUD SVD=BAUD | - |
| register_name_diff | UART3 | UART_DATA |  | 寄存器名不同：H=UART_DATA SVD=DATA | - |
| register_name_diff | UART3 | UART_IDE |  | 寄存器名不同：H=UART_IDE SVD=IDE | - |
| field_missing_in_svd | UART3 | UART_IDE | BKIE | SVD 缺少位域 UART3/UART_IDE/BKIE（H bit[3:3]） | 2442 |
| field_missing_in_header | UART3 | IDE | RXIE | H 文件未见位域 UART3/IDE/RXIE（仅 SVD 存在） | - |
| register_name_diff | SPI0 | SPI_CON |  | 寄存器名不同：H=SPI_CON SVD=CON | - |
| register_name_diff | SPI0 | SPI_STS |  | 寄存器名不同：H=SPI_STS SVD=STS | - |
| field_name_diff | SPI0 | SPI_STS | RINEIF | 位域名不同：H=RINEIF SVD=RXNEIF（bit 1） | - |
| field_missing_in_header | SPI0 | STS | TXHIF | H 文件未见位域 SPI0/STS/TXHIF（仅 SVD 存在） | - |
| register_name_diff | SPI0 | SPI_DATA |  | 寄存器名不同：H=SPI_DATA SVD=DATA | - |
| register_name_diff | SPI0 | SPI_IDE |  | 寄存器名不同：H=SPI_IDE SVD=IDE | - |
| field_name_diff | SPI0 | SPI_IDE | RXNEIE | 位域名不同：H=RXNEIE SVD=RXNELE（bit 1） | - |
| field_missing_in_header | SPI0 | IDE | TXDMAEN | H 文件未见位域 SPI0/IDE/TXDMAEN（仅 SVD 存在） | - |
| register_name_diff | SPI1 | SPI_CON |  | 寄存器名不同：H=SPI_CON SVD=CON | - |
| register_name_diff | SPI1 | SPI_STS |  | 寄存器名不同：H=SPI_STS SVD=STS | - |
| field_name_diff | SPI1 | SPI_STS | WCOL | 位域名不同：H=WCOL SVD=RXNEIF（bit 1） | - |
| field_missing_in_header | SPI1 | STS | TXEIF | H 文件未见位域 SPI1/STS/TXEIF（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | STS | RXFIF | H 文件未见位域 SPI1/STS/RXFIF（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | STS | RXHIF | H 文件未见位域 SPI1/STS/RXHIF（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | STS | TXHIF | H 文件未见位域 SPI1/STS/TXHIF（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | STS | WCOL | H 文件未见位域 SPI1/STS/WCOL（仅 SVD 存在） | - |
| register_name_diff | SPI1 | SPI_DATA |  | 寄存器名不同：H=SPI_DATA SVD=DATA | - |
| register_name_diff | SPI1 | SPI_IDE |  | 寄存器名不同：H=SPI_IDE SVD=IDE | - |
| field_missing_in_header | SPI1 | IDE | RXNELE | H 文件未见位域 SPI1/IDE/RXNELE（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | IDE | TBIE | H 文件未见位域 SPI1/IDE/TBIE（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | IDE | RXIE | H 文件未见位域 SPI1/IDE/RXIE（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | IDE | RXHIE | H 文件未见位域 SPI1/IDE/RXHIE（仅 SVD 存在） | - |
| field_missing_in_header | SPI1 | IDE | TXHIE | H 文件未见位域 SPI1/IDE/TXHIE（仅 SVD 存在） | - |
| register_name_diff | TWI0 | TWI_CON |  | 寄存器名不同：H=TWI_CON SVD=CON | - |
| register_name_diff | TWI0 | TWI_STS |  | 寄存器名不同：H=TWI_STS SVD=STS | - |
| field_name_diff | TWI0 | TWI_STS | TXERXE | 位域名不同：H=TXERXE SVD=TXnE_RXnE（bit 1） | - |
| register_name_diff | TWI0 | TWI_ADD |  | 寄存器名不同：H=TWI_ADD SVD=ADD | - |
| register_name_diff | TWI0 | TWI_DATA |  | 寄存器名不同：H=TWI_DATA SVD=DATA | - |
| register_name_diff | TWI0 | TWI_IDE |  | 寄存器名不同：H=TWI_IDE SVD=IDE | - |
| register_name_diff | TWI1 | TWI_CON |  | 寄存器名不同：H=TWI_CON SVD=CON | - |
| register_name_diff | TWI1 | TWI_STS |  | 寄存器名不同：H=TWI_STS SVD=STS | - |
| field_name_diff | TWI1 | TWI_STS | TXERXE | 位域名不同：H=TXERXE SVD=TXnE_RXnE（bit 1） | - |
| register_name_diff | TWI1 | TWI_ADD |  | 寄存器名不同：H=TWI_ADD SVD=ADD | - |
| register_name_diff | TWI1 | TWI_DATA |  | 寄存器名不同：H=TWI_DATA SVD=DATA | - |
| register_name_diff | TWI1 | TWI_IDE |  | 寄存器名不同：H=TWI_IDE SVD=IDE | - |
| register_name_diff | TIM0 | TIM_CON |  | 寄存器名不同：H=TIM_CON SVD=CON | - |
| field_name_diff | TIM0 | TIM_CON | TIMCLK | 位域名不同：H=TIMCLK SVD=TIMCK（bit 8） | - |
| register_name_diff | TIM0 | TIM_CNT |  | 寄存器名不同：H=TIM_CNT SVD=CNT | - |
| register_name_diff | TIM0 | TIM_RLD |  | 寄存器名不同：H=TIM_RLD SVD=RLD | - |
| register_name_diff | TIM0 | TIM_STS |  | 寄存器名不同：H=TIM_STS SVD=STS | - |
| register_name_diff | TIM0 | TIM_PDTA_RCAP |  | 寄存器名不同：H=TIM_PDTA_RCAP SVD=PDTA_RCAP | - |
| register_name_diff | TIM0 | TIM_PDTB_FCAP |  | 寄存器名不同：H=TIM_PDTB_FCAP SVD=PDTB_FCAP | - |
| register_name_diff | TIM0 | TIM_IDE |  | 寄存器名不同：H=TIM_IDE SVD=IDE | - |
| field_name_diff | TIM0 | TIM_IDE | EXIRE | 位域名不同：H=EXIRE SVD=EXRIE（bit 2） | - |
| field_name_diff | TIM0 | TIM_IDE | EXIFE | 位域名不同：H=EXIFE SVD=EXFIE（bit 3） | - |
| register_name_diff | TIM1 | TIM_CON |  | 寄存器名不同：H=TIM_CON SVD=CON | - |
| field_name_diff | TIM1 | TIM_CON | TIMCLK | 位域名不同：H=TIMCLK SVD=TIMCK（bit 8） | - |
| register_name_diff | TIM1 | TIM_CNT |  | 寄存器名不同：H=TIM_CNT SVD=CNT | - |
| register_name_diff | TIM1 | TIM_RLD |  | 寄存器名不同：H=TIM_RLD SVD=RLD | - |
| register_name_diff | TIM1 | TIM_STS |  | 寄存器名不同：H=TIM_STS SVD=STS | - |
| register_name_diff | TIM1 | TIM_PDTA_RCAP |  | 寄存器名不同：H=TIM_PDTA_RCAP SVD=PDTA_RCAP | - |
| register_name_diff | TIM1 | TIM_PDTB_FCAP |  | 寄存器名不同：H=TIM_PDTB_FCAP SVD=PDTB_FCAP | - |
| register_name_diff | TIM1 | TIM_IDE |  | 寄存器名不同：H=TIM_IDE SVD=IDE | - |
| field_name_diff | TIM1 | TIM_IDE | EXIRE | 位域名不同：H=EXIRE SVD=EXRIE（bit 2） | - |
| field_name_diff | TIM1 | TIM_IDE | EXIFE | 位域名不同：H=EXIFE SVD=EXFIE（bit 3） | - |
| register_name_diff | TIM2 | TIM_CON |  | 寄存器名不同：H=TIM_CON SVD=CON | - |
| field_name_diff | TIM2 | TIM_CON | TIMCLK | 位域名不同：H=TIMCLK SVD=TIMCK（bit 8） | - |
| register_name_diff | TIM2 | TIM_CNT |  | 寄存器名不同：H=TIM_CNT SVD=CNT | - |
| register_name_diff | TIM2 | TIM_RLD |  | 寄存器名不同：H=TIM_RLD SVD=RLD | - |
| register_name_diff | TIM2 | TIM_STS |  | 寄存器名不同：H=TIM_STS SVD=STS | - |
| register_name_diff | TIM2 | TIM_PDTA_RCAP |  | 寄存器名不同：H=TIM_PDTA_RCAP SVD=PDTA_RCAP | - |
| register_name_diff | TIM2 | TIM_PDTB_FCAP |  | 寄存器名不同：H=TIM_PDTB_FCAP SVD=PDTB_FCAP | - |
| register_name_diff | TIM2 | TIM_IDE |  | 寄存器名不同：H=TIM_IDE SVD=IDE | - |
| field_name_diff | TIM2 | TIM_IDE | EXIRE | 位域名不同：H=EXIRE SVD=EXRIE（bit 2） | - |
| field_name_diff | TIM2 | TIM_IDE | EXIFE | 位域名不同：H=EXIFE SVD=EXFIE（bit 3） | - |
| register_name_diff | TIM3 | TIM_CON |  | 寄存器名不同：H=TIM_CON SVD=CON | - |
| field_name_diff | TIM3 | TIM_CON | TIMCLK | 位域名不同：H=TIMCLK SVD=TIMCK（bit 8） | - |
| register_name_diff | TIM3 | TIM_CNT |  | 寄存器名不同：H=TIM_CNT SVD=CNT | - |
| register_name_diff | TIM3 | TIM_RLD |  | 寄存器名不同：H=TIM_RLD SVD=RLD | - |
| register_name_diff | TIM3 | TIM_STS |  | 寄存器名不同：H=TIM_STS SVD=STS | - |
| register_name_diff | TIM3 | TIM_PDTA_RCAP |  | 寄存器名不同：H=TIM_PDTA_RCAP SVD=PDTA_RCAP | - |
| register_name_diff | TIM3 | TIM_PDTB_FCAP |  | 寄存器名不同：H=TIM_PDTB_FCAP SVD=PDTB_FCAP | - |
| register_name_diff | TIM3 | TIM_IDE |  | 寄存器名不同：H=TIM_IDE SVD=IDE | - |
| field_name_diff | TIM3 | TIM_IDE | EXIRE | 位域名不同：H=EXIRE SVD=EXRIE（bit 2） | - |
| field_name_diff | TIM3 | TIM_IDE | EXIFE | 位域名不同：H=EXIFE SVD=EXFIE（bit 3） | - |
| register_name_diff | TIM4 | TIM_CON |  | 寄存器名不同：H=TIM_CON SVD=CON | - |
| field_name_diff | TIM4 | TIM_CON | TIMCLK | 位域名不同：H=TIMCLK SVD=TIMCK（bit 8） | - |
| register_name_diff | TIM4 | TIM_CNT |  | 寄存器名不同：H=TIM_CNT SVD=CNT | - |
| register_name_diff | TIM4 | TIM_RLD |  | 寄存器名不同：H=TIM_RLD SVD=RLD | - |
| register_name_diff | TIM4 | TIM_STS |  | 寄存器名不同：H=TIM_STS SVD=STS | - |
| register_name_diff | TIM4 | TIM_PDTA_RCAP |  | 寄存器名不同：H=TIM_PDTA_RCAP SVD=PDTA_RCAP | - |
| register_name_diff | TIM4 | TIM_PDTB_FCAP |  | 寄存器名不同：H=TIM_PDTB_FCAP SVD=PDTB_FCAP | - |
| register_name_diff | TIM4 | TIM_IDE |  | 寄存器名不同：H=TIM_IDE SVD=IDE | - |
| field_name_diff | TIM4 | TIM_IDE | EXIRE | 位域名不同：H=EXIRE SVD=EXRIE（bit 2） | - |
| field_name_diff | TIM4 | TIM_IDE | EXIFE | 位域名不同：H=EXIFE SVD=EXFIE（bit 3） | - |
| register_name_diff | TIM5 | TIM_CON |  | 寄存器名不同：H=TIM_CON SVD=CON | - |
| field_name_diff | TIM5 | TIM_CON | TIMCLK | 位域名不同：H=TIMCLK SVD=TIMCK（bit 8） | - |
| register_name_diff | TIM5 | TIM_CNT |  | 寄存器名不同：H=TIM_CNT SVD=CNT | - |