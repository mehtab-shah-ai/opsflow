import { useEffect, useRef } from 'react'
import * as echarts from 'echarts/core'
import { BarChart, LineChart, PieChart, ScatterChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { ChartSpec } from './types'
echarts.use([BarChart,LineChart,PieChart,ScatterChart,GridComponent,TooltipComponent,LegendComponent,AriaComponent,CanvasRenderer])
const colors=['#277B63','#C0DDB1','#C7A46B','#84B3BF','#8C92B0']
export default function Chart({spec,compact=false}:{spec:ChartSpec;compact?:boolean}) {
  const ref=useRef<HTMLDivElement>(null)
  useEffect(()=>{
    if (!ref.current || !spec.data.length) return
    const chart=echarts.init(ref.current)
    const pie=spec.type==='donut', scatter=spec.type==='scatter'
    const option={color:colors,textStyle:{fontFamily:'Inter',fontSize:11,color:'#64756C'},animationDuration:450,aria:{enabled:true,description:`${spec.title}. ${spec.subtitle}`},tooltip:{trigger:pie||scatter?'item':'axis',confine:true,renderMode:'richText'},legend:{bottom:0,icon:'circle',itemWidth:8,itemHeight:8,textStyle:{fontSize:10}},grid:{left:42,right:18,top:20,bottom:65,containLabel:false},
      ...(pie?{}:{xAxis:{type:scatter?'value':'category',data:scatter?undefined:spec.data.map(d=>String(d[spec.x])),axisLine:{lineStyle:{color:'#DFE6DF'}},axisTick:{show:false},axisLabel:{fontSize:10,hideOverlap:true,width:90,overflow:'truncate'}},yAxis:{type:'value',splitLine:{lineStyle:{color:'#EEF1EC',type:'dashed'}},axisLabel:{fontSize:10}}}),
      series:pie?[{type:'pie',radius:['52%','75%'],center:['50%','43%'],label:{show:false},itemStyle:{borderRadius:4,borderWidth:3,borderColor:'#fff'},data:spec.data.map(d=>({name:String(d[spec.x]),value:Number(d[spec.series[0]])}))}]:spec.series.map((s,i)=>({name:s.replaceAll('_',' '),type:spec.type==='line'?'line':scatter?'scatter':'bar',smooth:spec.type==='line',symbolSize:6,barMaxWidth:28,itemStyle:{borderRadius:spec.type==='bar'?[4,4,0,0]:0},lineStyle:{width:3},areaStyle:spec.type==='line'?{opacity:.06}:undefined,data:spec.data.map(d=>scatter?[Number(d.x),Number(d.y)]:Number(d[s])),color:colors[i%colors.length]}))}
    chart.setOption(option)
    const observer=new ResizeObserver(()=>chart.resize());observer.observe(ref.current)
    return()=>{observer.disconnect();chart.dispose()}
  },[spec])
  return spec.data.length?<div className={`chart ${compact?'compact':''}`} ref={ref} role="img" aria-label={`${spec.title}. ${spec.subtitle}`}/>:<div className="empty-chart">No compatible values found in this table.</div>
}
