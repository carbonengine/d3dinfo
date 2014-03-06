import blue

from . import _trinity as trinity
from .renderJob import renderJobs, CreateRenderJob


class GraphManager:
    """
    GraphManager manages the render job to render performance graphs in Trinity
    """
    def __init__(self):
        self.isEnabled = False
        self.renderJobContainer = None
        self.renderJob = None
        self.graphGroups = {}
        self.graphs = {}
        self.bounds = (0, 0, 400, 400)
        
        renderer = trinity.TriStepRenderLineGraph()
        renderer.name = 'time'
        renderer.legendScale = 1000.0
        renderer.maxLegend = 300.0
        
        grp = {}
        grp['viewport'] = trinity.TriViewport()
        grp['renderer'] = renderer
        grp['graphs'] = []
        self.graphGroups['time'] = grp

        renderer = trinity.TriStepRenderLineGraph()
        renderer.name = 'counterLow'
        
        grp = {}
        grp['viewport'] = trinity.TriViewport()
        grp['renderer'] = renderer
        grp['graphs'] = []
        self.graphGroups['counterLow'] = grp

        renderer = trinity.TriStepRenderLineGraph()
        renderer.name = 'counterHigh'
        
        grp = {}
        grp['viewport'] = trinity.TriViewport()
        grp['renderer'] = renderer
        grp['graphs'] = []
        self.graphGroups['counterHigh'] = grp

        renderer = trinity.TriStepRenderLineGraph()
        renderer.name = 'memory'
        renderer.legendScale = 0.000001
        
        grp = {}
        grp['viewport'] = trinity.TriViewport()
        grp['renderer'] = renderer
        grp['graphs'] = []
        self.graphGroups['memory'] = grp
        
        self.AdjustViewports(self.bounds)
        
        """
        Colors are assigned automatically to graphs. We allow up to 10 graphs
        per category and simply maintain a list of available colors for each
        category. A color is removed from this list when a graph is added
        and when the graph is removed the color is added back. This ensures
        that no two graphs in the same category have the same color.
        """
        self.colors = { 'counterHigh':[], 'counterLow':[], 'time':[], 'memory':[] }

        availColors = [
            (0.8, 0.8, 0.8, 1.0),
            (0.4, 0.8, 0.8, 1.0),
            (0.8, 0.4, 0.8, 1.0),
            (0.4, 0.4, 0.8, 1.0),
            (0.8, 0.8, 0.4, 1.0),
            (0.4, 0.8, 0.4, 1.0),
            (0.8, 0.4, 0.4, 1.0),
            (0.8, 0.0, 0.0, 1.0),
            (0.0, 0.8, 0.8, 1.0),
            (0.8, 0.8, 0.0, 1.0)
        ]
        
        for each in availColors:
            self.colors['counterHigh'].append(each)
            self.colors['counterLow'].append(each)
            self.colors['time'].append(each)
            self.colors['memory'].append(each)
        
    def AdjustViewports(self, bounds):
        """
        Adjusts the viewports according to the given bounds.
        Graphs are rendered in four groups - this divides the available
        space evenly between those groups.
        """
        self.bounds = bounds
        width = bounds[2]
        height = bounds[3]

        counts = {}
        for key, val in self.graphGroups.iteritems():
            counts[key] = len(val['graphs'])
            
        grpCount = 0
        for each in counts.values():
            if each > 0:
                grpCount += 1
        
        margin = 4
        grpHeight = 0
        if grpCount > 0:
            grpHeight = (height - ((grpCount - 1) * margin)) / grpCount

        y = margin + self.bounds[1]
        for key, val in self.graphGroups.iteritems():
            vp = self.graphGroups[key]['viewport']
            if counts[key] > 0:
                vp.x = self.bounds[0]
                vp.y = y
                vp.width = width - margin * 2
                vp.height = grpHeight
                
                y += grpHeight + margin
            else:
                vp.x = 1
                vp.y = 1
                vp.width = 10
                vp.height = 10
        
    def SetEnabled(self, enable):
        if self.isEnabled == enable:
            return
            
        if enable:
            self.renderJob = self.AssembleRenderJob()
            if self.renderJobContainer:
                self.renderJobContainer.steps.append(self.renderJob)
            else:
                renderJobs.recurring.append(self.renderJob)
        else:
            try:
                if self.renderJobContainer:
                    self.renderJobContainer.steps.remove(self.renderJob)
                else:
                    renderJobs.recurring.remove(self.renderJob)
            except blue.error:
                pass
            self.renderJob = None
        self.isEnabled = enable
        
    def IsEnabled(self):
        return self.isEnabled

    def AssembleRenderJob(self):
        renderJob = CreateRenderJob('Graphs')
        for grp in self.graphGroups.values():
            renderJob.SetViewport(grp['viewport'])
            renderJob.steps.append(grp['renderer'])
        return renderJob
        
    # Add a graph for the given statistic and return the Tr2LineGraph
    # object used. If the graph has already been added, simply returns
    # the Tr2LineGraph object.
    def AddGraph(self, statisticName):
        if self.graphs.has_key(statisticName):
            print statisticName, "is already being graphed"
            return self.graphs[statisticName][1]
            
        lg = blue.statistics.GetAccumulator(statisticName)
        if lg is not None:
            print statisticName, "already has an accumulator"
            return lg
            
        statsDesc = blue.statistics.GetDescriptions()
        grpName = statsDesc[statisticName][1]
        if len(self.colors[grpName]) == 0:
            raise Exception("Too many graphs per category")
            
        grp = self.graphGroups[grpName]
        grp['graphs'].append(statisticName)

        lg = trinity.Tr2LineGraph()
        lg.name = statisticName
        lg.color = self.colors[grpName].pop()
        blue.statistics.SetAccumulator(statisticName, lg)

        renderer = grp['renderer']
        renderer.lineGraphs.append(lg)
        self.graphs[statisticName] = [grp, lg]
        
        self.AdjustViewports(self.bounds)
        
        return lg
        
    def RemoveGraph(self, statisticName):
        blue.statistics.SetAccumulator(statisticName, None)
        entry = self.graphs[statisticName]
        grp = entry[0]
        lg = entry[1]
        grp['renderer'].lineGraphs.fremove(lg)
        del(self.graphs[statisticName])
        grp['graphs'].remove(statisticName)
        statsDesc = blue.statistics.GetDescriptions()
        grpName = statsDesc[statisticName][1]
        self.colors[grpName].append(lg.color)
        self.AdjustViewports(self.bounds)
        
    def HasGraph(self, statisticName):
        return self.graphs.has_key(statisticName)
        
    def Clear(self):
        while len(self.graphs) > 0:
            self.RemoveGraph(self.graphs.keys()[0])
        
    def AddMarker(self, statisticName, name):
        if not self.graphs.has_key(statisticName):
            return
            
        self.graphs[statisticName][1].AddMarker(name)
