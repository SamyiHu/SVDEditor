"""Generate a test SVD file with 50 peripherals."""
import xml.etree.ElementTree as ET

device = ET.Element("device", schemaVersion="1.3",
    **{"xmlns:xs": "http://www.w3.org/2001/XMLSchema-instance",
       "xs:noNamespaceSchemaLocation": "CMSIS-SVD.xsd"})

for tag, val in [("name","STM32F407Test"),("version","1.0"),
    ("description","Test device with 50 peripherals"),
    ("addressUnitBits","8"),("width","32"),("size","32"),
    ("access","read-write"),("resetValue","0x00000000"),("resetMask","0xFFFFFFFF")]:
    ET.SubElement(device, tag).text = val

peripherals = ET.SubElement(device, "peripherals")

def make_fields(parent, fields):
    fe = ET.SubElement(parent, "fields")
    for fn, fo, fw in fields:
        f = ET.SubElement(fe, "field")
        ET.SubElement(f, "name").text = fn
        ET.SubElement(f, "description").text = f"Field {fn}"
        ET.SubElement(f, "bitOffset").text = str(fo)
        ET.SubElement(f, "bitWidth").text = str(fw)

def make_periph(name, base, desc, registers):
    p = ET.SubElement(peripherals, "peripheral")
    ET.SubElement(p, "name").text = name
    ET.SubElement(p, "baseAddress").text = base
    ET.SubElement(p, "description").text = desc
    re = ET.SubElement(p, "registers")
    for rn, ro, rd, rf in registers:
        reg = ET.SubElement(re, "register")
        ET.SubElement(reg, "name").text = rn
        ET.SubElement(reg, "description").text = rd
        ET.SubElement(reg, "addressOffset").text = ro
        ET.SubElement(reg, "size").text = "0x20"
        ET.SubElement(reg, "access").text = "read-write"
        ET.SubElement(reg, "resetValue").text = "0x00000000"
        make_fields(reg, rf)

def derive(name, base, desc, from_):
    p = ET.SubElement(peripherals, "peripheral", derivedFrom=from_)
    ET.SubElement(p, "name").text = name
    ET.SubElement(p, "baseAddress").text = base
    ET.SubElement(p, "description").text = desc

# --- GPIO (9 ports) ---
gpio_regs = [
    ("MODER","0x00","Port mode register",[("MODE0",0,2),("MODE1",2,2),("MODE2",4,2),("MODE3",6,2),("MODE4",8,2),("MODE5",10,2),("MODE6",12,2),("MODE7",14,2)]),
    ("OTYPER","0x04","Port output type register",[("OT0",0,1),("OT1",1,1),("OT2",2,1),("OT3",3,1)]),
    ("OSPEEDR","0x08","Port output speed register",[("OSPEED0",0,2),("OSPEED1",2,2)]),
    ("PUPDR","0x0C","Port pull-up/pull-down register",[("PUPD0",0,2),("PUPD1",2,2)]),
    ("IDR","0x10","Port input data register",[("ID0",0,1),("ID1",1,1)]),
    ("ODR","0x14","Port output data register",[("OD0",0,1),("OD1",1,1)]),
    ("BSRR","0x18","Port bit set/reset register",[("BS0",0,1),("BR0",16,1)]),
    ("LCKR","0x1C","Port configuration lock register",[("LCK0",0,1),("LCKK",16,1)]),
    ("AFRL","0x20","Alternate function low register",[("AFSEL0",0,4),("AFSEL1",4,4)]),
    ("AFRH","0x24","Alternate function high register",[("AFSEL8",0,4),("AFSEL9",4,4)]),
]
make_periph("GPIOA","0x40020000","General-purpose I/O port A",gpio_regs)
for i,l in enumerate("BCDEFGHI"):
    derive(f"GPIO{l}",f"0x40020{0x400*(i+1):04X}",f"General-purpose I/O port {l}","GPIOA")

# --- DMA (2) ---
dma_regs = [
    ("ISR","0x00","DMA interrupt status register",[("TCIF1",1,1),("HTIF1",3,1),("TEIF1",5,1)]),
    ("IFCR","0x04","DMA interrupt flag clear register",[("CTCIF1",1,1),("CHTIF1",3,1)]),
    ("CCR1","0x08","DMA channel 1 configuration",[("EN",0,1),("TCIE",1,1),("HTIE",2,1),("TEIE",3,1),("DIR",4,1),("CIRC",5,1),("MINC",7,1),("PSIZE",8,2),("PL",12,2)]),
    ("CNDTR1","0x0C","DMA channel 1 number of data",[("NDT",0,16)]),
    ("CPAR1","0x10","DMA channel 1 peripheral address",[("PA",0,32)]),
    ("CMAR1","0x14","DMA channel 1 memory address",[("MA",0,32)]),
]
make_periph("DMA1","0x40026000","DMA controller 1",dma_regs)
derive("DMA2","0x40026400","DMA controller 2","DMA1")

# --- CRC ---
make_periph("CRC","0x40023000","CRC calculation unit",[
    ("DR","0x00","CRC data register",[("DR",0,32)]),
    ("IDR","0x04","CRC independent data register",[("IDR",0,8)]),
    ("CR","0x08","CRC control register",[("RESET",0,1),("POLYSIZE",3,2),("REV_IN",5,2)]),
])

# --- RCC ---
make_periph("RCC","0x40023800","Reset and clock control",[
    ("CR","0x00","Clock control register",[("HSION",0,1),("HSIRDY",1,1),("HSEON",16,1),("HSERDY",17,1),("PLLON",24,1),("PLLRDY",25,1)]),
    ("PLLCFGR","0x04","PLL configuration register",[("PLLM",0,6),("PLLN",6,9),("PLLP",16,2),("PLLSRC",22,1),("PLLQ",24,4)]),
    ("CFGR","0x08","Clock configuration register",[("SW",0,2),("SWS",2,2),("HPRE",4,4),("PPRE1",10,3),("PPRE2",13,3)]),
    ("AHB1ENR","0x30","AHB1 peripheral clock enable",[("GPIOAEN",0,1),("GPIOBEN",1,1),("CRCEN",12,1),("DMA1EN",21,1)]),
    ("APB1ENR","0x40","APB1 peripheral clock enable",[("TIM2EN",0,1),("SPI2EN",14,1),("USART2EN",17,1),("I2C1EN",21,1)]),
    ("APB2ENR","0x44","APB2 peripheral clock enable",[("TIM1EN",0,1),("USART1EN",4,1),("SPI1EN",12,1),("ADC1EN",8,1)]),
])

# --- TIM1 ---
make_periph("TIM1","0x40010000","Advanced-control timer 1",[
    ("CR1","0x00","Control register 1",[("CEN",0,1),("UDIS",1,1),("URS",2,1),("DIR",4,1),("ARPE",7,1)]),
    ("CR2","0x04","Control register 2",[("CCPC",0,1),("MMS",4,3),("TI1S",7,1)]),
    ("SMCR","0x08","Slave mode control register",[("SMS",0,3),("TS",4,3),("MSM",7,1)]),
    ("DIER","0x0C","DMA/interrupt enable register",[("UIE",0,1),("CC1IE",1,1),("TIE",6,1)]),
    ("SR","0x10","Status register",[("UIF",0,1),("CC1IF",1,1),("TIF",6,1)]),
    ("PSC","0x28","Prescaler",[("PSC",0,16)]),
    ("ARR","0x2C","Auto-reload register",[("ARR",0,16)]),
    ("CCR1","0x34","Capture/compare register 1",[("CCR1",0,16)]),
    ("BDTR","0x44","Break and dead-time register",[("DTG",0,8),("LOCK",8,2),("MOE",15,1)]),
])

# --- TIM2-5, 9-11 (7) ---
tim2_regs = [
    ("CR1","0x00","Control register 1",[("CEN",0,1),("UDIS",1,1),("ARPE",7,1)]),
    ("DIER","0x0C","DMA/interrupt enable register",[("UIE",0,1),("CC1IE",1,1)]),
    ("SR","0x10","Status register",[("UIF",0,1),("CC1IF",1,1)]),
    ("PSC","0x28","Prescaler",[("PSC",0,16)]),
    ("ARR","0x2C","Auto-reload register",[("ARR",0,32)]),
]
make_periph("TIM2","0x40000000","General-purpose timer 2",tim2_regs)
for n,ba in [("TIM3","0x40000400"),("TIM4","0x40000800"),("TIM5","0x40000C00"),
             ("TIM9","0x40014000"),("TIM10","0x40014400"),("TIM11","0x40014800")]:
    derive(n,ba,f"General-purpose timer {n[3:]}","TIM2")

# --- USART/UART (6) ---
usart_regs = [
    ("SR","0x00","Status register",[("PE",0,1),("FE",1,1),("RXNE",5,1),("TC",6,1),("TXE",7,1)]),
    ("DR","0x04","Data register",[("DR",0,9)]),
    ("BRR","0x08","Baud rate register",[("DIV_Mantissa",0,12),("DIV_Fraction",16,4)]),
    ("CR1","0x0C","Control register 1",[("RE",2,1),("TE",3,1),("RXNEIE",5,1),("TXEIE",7,1),("UE",13,1)]),
    ("CR2","0x10","Control register 2",[("STOP",12,2),("LINEN",14,1)]),
    ("CR3","0x14","Control register 3",[("DMAR",6,1),("DMAT",7,1),("CTSE",9,1)]),
]
make_periph("USART1","0x40011000","USART 1",usart_regs)
for n,ba in [("USART2","0x40004400"),("USART3","0x40004800"),("UART4","0x40004C00"),
             ("UART5","0x40005000"),("USART6","0x40011400")]:
    derive(n,ba,f"{n}","USART1")

# --- SPI (3) ---
spi_regs = [
    ("CR1","0x00","Control register 1",[("CPHA",0,1),("CPOL",1,1),("MSTR",2,1),("BR",3,3),("SPE",6,1),("LSBFIRST",7,1)]),
    ("CR2","0x04","Control register 2",[("RXDMAEN",0,1),("TXDMAEN",1,1),("SSOE",2,1)]),
    ("SR","0x08","Status register",[("RXNE",0,1),("TXE",1,1),("BSY",7,1)]),
    ("DR","0x0C","Data register",[("DR",0,16)]),
]
make_periph("SPI1","0x40013000","SPI 1",spi_regs)
derive("SPI2","0x40003800","SPI 2","SPI1")
derive("SPI3","0x40003C00","SPI 3","SPI1")

# --- I2C (3) ---
i2c_regs = [
    ("CR1","0x00","Control register 1",[("PE",0,1),("START",8,1),("STOP",9,1),("ACK",10,1)]),
    ("CR2","0x04","Control register 2",[("ITEVTEN",0,1),("ITBUFEN",1,1),("DMAEN",11,1)]),
    ("SR1","0x08","Status register 1",[("SB",0,1),("ADDR",1,1),("RXNE",6,1),("TXE",7,1)]),
    ("SR2","0x0C","Status register 2",[("BUSY",1,1),("TRA",2,1)]),
    ("CCR","0x14","Clock control register",[("CCR",0,12),("F_S",15,1)]),
]
make_periph("I2C1","0x40005400","I2C 1",i2c_regs)
derive("I2C2","0x40005800","I2C 2","I2C1")
derive("I2C3","0x40005C00","I2C 3","I2C1")

# --- ADC (3) ---
adc_regs = [
    ("SR","0x00","Status register",[("EOC",1,1),("STRT",4,1)]),
    ("CR1","0x04","Control register 1",[("SCAN",8,1),("RES",24,2)]),
    ("CR2","0x08","Control register 2",[("ADON",0,1),("CONT",1,1),("DMA",8,1),("SWSTART",30,1)]),
    ("DR","0x4C","Regular data register",[("DATA",0,16)]),
]
make_periph("ADC1","0x40012000","ADC 1",adc_regs)
derive("ADC2","0x40012100","ADC 2","ADC1")
derive("ADC3","0x40012200","ADC 3","ADC1")

# --- DAC ---
make_periph("DAC","0x40007400","Digital-to-analog converter",[
    ("CR","0x00","Control register",[("EN1",0,1),("TEN1",2,1),("DMAEN1",12,1),("EN2",16,1)]),
    ("DHR12R1","0x08","Channel 1 12-bit data",[("DACC1DHR",0,12)]),
    ("DOR1","0x2C","Channel 1 data output",[("DACC1DOR",0,12)]),
])

# --- SYSCFG ---
make_periph("SYSCFG","0x40013800","System configuration controller",[
    ("MEMRMP","0x00","Memory remap register",[("MEM_MODE",0,2)]),
    ("EXTICR1","0x08","External interrupt config 1",[("EXTI0",0,4),("EXTI1",4,4)]),
    ("CMPCR","0x20","Compensation cell control",[("CMP_PD",0,1),("READY",8,1)]),
])

# --- EXTI ---
make_periph("EXTI","0x40013C00","External interrupt/event controller",[
    ("IMR","0x00","Interrupt mask register",[("MR0",0,1),("MR1",1,1),("MR2",2,1)]),
    ("RTSR","0x08","Rising trigger selection",[("TR0",0,1),("TR1",1,1)]),
    ("FTSR","0x0C","Falling trigger selection",[("TR0",0,1),("TR1",1,1)]),
    ("PR","0x14","Pending register",[("PR0",0,1),("PR1",1,1)]),
])

# --- NVIC ---
make_periph("NVIC","0xE000E100","Nested vectored interrupt controller",[
    ("ISER0","0x00","Interrupt set-enable 0",[("SETENA",0,32)]),
    ("ICER0","0x80","Interrupt clear-enable 0",[("CLRENA",0,32)]),
    ("ISPR0","0x100","Interrupt set-pending 0",[("SETPEND",0,32)]),
])

# --- SCB ---
make_periph("SCB","0xE000ED00","System control block",[
    ("CPUID","0x00","CPUID base register",[("Revision",0,4),("PartNo",4,12),("Implementer",24,8)]),
    ("ICSR","0x04","Interrupt control state",[("VECTACTIVE",0,9),("PENDSTSET",26,1),("PENDSVSET",28,1)]),
    ("AIRCR","0x0C","Application interrupt reset control",[("VECTKEY",16,16),("PRIGROUP",8,3),("SYSRESETREQ",2,1)]),
])

# --- FLASH ---
make_periph("FLASH","0x40023C00","Flash memory interface",[
    ("ACR","0x00","Flash access control",[("LATENCY",0,3),("PRFTEN",8,1),("ICEN",9,1),("DCEN",10,1)]),
    ("SR","0x0C","Flash status register",[("BSY",0,1),("PGSERR",2,1),("WRPERR",5,1)]),
    ("CR","0x10","Flash control register",[("PG",0,1),("SER",1,1),("MER",2,1),("STRT",16,1),("LOCK",31,1)]),
])

# --- PWR ---
make_periph("PWR","0x40007000","Power controller",[
    ("CR","0x00","Power control register",[("LPDS",0,1),("PDDS",1,1),("PVDE",4,1),("DBP",8,1)]),
    ("CSR","0x04","Power status register",[("WUF",0,1),("SBF",1,1),("PVDO",2,1)]),
])

# --- RTC ---
make_periph("RTC","0x40002800","Real-time clock",[
    ("TR","0x00","Time register",[("SU",0,4),("ST",4,3),("MNU",8,4),("HU",16,4)]),
    ("DR","0x04","Date register",[("DU",0,4),("MU",8,4),("YU",16,4)]),
    ("CR","0x08","Control register",[("FMT",6,1)]),
    ("ISR","0x0C","Init and status register",[("RSF",3,1),("INIT",7,1)]),
    ("PRER","0x10","Prescaler register",[("PREDIV_S",0,15),("PREDIV_A",16,7)]),
])

# --- IWDG ---
make_periph("IWDG","0x40003000","Independent watchdog",[
    ("KR","0x00","Key register",[("KEY",0,16)]),
    ("PR","0x04","Prescaler register",[("PR",0,3)]),
    ("RLR","0x08","Reload register",[("RL",0,12)]),
    ("SR","0x0C","Status register",[("PVU",0,1),("RVU",1,1)]),
])

# --- WWDG ---
make_periph("WWDG","0x40002C00","Window watchdog",[
    ("CR","0x00","Control register",[("T",0,7),("WDGA",7,1)]),
    ("CFR","0x04","Configuration register",[("W",0,7),("WDGTB",7,2),("EWI",9,1)]),
    ("SR","0x08","Status register",[("EWIF",0,1)]),
])

# --- CAN (2) ---
can_regs = [
    ("MCR","0x00","Master control register",[("INRQ",0,1),("SLEEP",1,1),("NART",4,1),("ABOM",6,1)]),
    ("MSR","0x04","Master status register",[("INAK",0,1),("SLAK",1,1),("ERRI",2,1)]),
    ("BTR","0x1C","Bit timing register",[("BRP",0,10),("TS1",16,4),("TS2",20,3)]),
]
make_periph("CAN1","0x40006400","CAN 1",can_regs)
derive("CAN2","0x40006800","CAN 2","CAN1")

# --- OTG_FS ---
make_periph("OTG_FS","0x50000000","USB OTG full speed",[
    ("GOTGCTL","0x000","OTG control",[("SRQSCS",0,1),("HNPRQ",9,1)]),
    ("GAHBCFG","0x008","AHB configuration",[("GINT",0,1)]),
    ("GUSBCFG","0x00C","USB configuration",[("PHYSEL",6,1),("FDMOD",30,1)]),
])

# --- ETHERNET_MAC ---
make_periph("ETHERNET_MAC","0x40028000","Ethernet MAC",[
    ("MACCR","0x00","MAC configuration",[("RE",2,1),("TE",3,1),("DM",11,1)]),
    ("MACMIIAR","0x10","MAC MII address",[("PA",11,5),("MR",6,5)]),
    ("MACMIIDR","0x14","MAC MII data",[("MD",0,16)]),
])

# --- RNG ---
make_periph("RNG","0x50060800","Random number generator",[
    ("CR","0x00","Control register",[("RNGEN",2,1),("IE",3,1)]),
    ("SR","0x04","Status register",[("DRDY",0,1),("CECS",1,1),("SECS",2,1)]),
    ("DR","0x08","Data register",[("RNDATA",0,32)]),
])

# --- DBGMCU ---
make_periph("DBGMCU","0xE0042000","Debug MCU",[
    ("IDCODE","0x00","Device identifier",[("DEV_ID",0,12),("REV_ID",16,16)]),
    ("CR","0x04","Debug configuration",[("DBG_SLEEP",0,1),("DBG_STOP",1,1),("TRACE_IOEN",5,2)]),
])

# --- Write ---
ET.indent(tree=ET.ElementTree(device), space="  ")
tree = ET.ElementTree(device)
ET.indent(tree, space="  ")
tree.write("d:/AItool/SVDEditor/test_data/test_50peripherals.svd",
           encoding="utf-8", xml_declaration=True)

# Count
import xml.etree.ElementTree as ET2
root = ET2.parse("d:/AItool/SVDEditor/test_data/test_50peripherals.svd").getroot()
count = len(root.findall(".//peripheral"))
print(f"Generated SVD with {count} peripherals")
