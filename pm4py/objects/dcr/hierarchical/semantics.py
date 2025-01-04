from typing import Set

from pm4py.objects.dcr.extended.semantics import ExtendedSemantics
from pm4py.objects.dcr.obj import DcrGraph

class HierarchicalSemantics(ExtendedSemantics):  
    
    # Take an element in a set and return it as a string without curly braces
    # We need to reformat the string to use the element as a key
    # parameters 
    #   s : str - String to be converted from dict entry to string
    @classmethod
    def setElemToString(cls, s : str):
        return str(s).replace("{'", "").replace("'}","")
    
    # Finds the groups an event belongs to
    # parameters
    #   dictionary : dict - the dictionary to find the key in
    #   value : str - the value which the reverse search should find the key
    @classmethod
    def find_groups(cls, dictionary : dict , value : str) -> Set[str]:
        keys = set()
        def recursive(d, v):
            for key, val in list(d.items()):        
                if v in val:
                    keys.add(key)
                    recursive(d, key)
        recursive(dictionary, value)
        return keys

    # Flattens groups nested in other groups (just like np.array[...].flatten().toList())
    # Make use of a recursive function "recusive" to achieve n-nested groups
    # parameters 
    #   Graph : DcrGraph 
    #   group : Any 
    @classmethod
    def flattenNestedGroup(cls, graph : DcrGraph, group) -> Set[str]:
            nestGroups : dict = graph.nestedgroups
            nested_keys : Set = set(nestGroups.keys())
            flattenedGroup : Set[str] = set()
            def recursive(group):
                for event in group:
                    if cls.setElemToString(event) in nested_keys:
                        nestedGroup : Set[str] = nestGroups[event]
                        recursive(nestedGroup)
                    else:
                        flattenedGroup.add(event)
            recursive(group)
            return flattenedGroup
       
    # Updates graph when executing an event
    # Takes care of the different combinations events (and nested graphs) can have
    # e.g. nested -> nested, single event -> nested etc.
    # This is done for the relations of response, exclude and include
    # parameters 
    #   graph : DcrGraph, 
    #   event : Any - Can be a single event or a nested graph
    #   nestedKeys : Set[str] - The names of the groups 
    #   nestedGroups : dict[str, Set[str]] - key is nestedKeys, values is groups for nestedKeys
    @classmethod 
    def execute_helper(cls, graph, event, nestedKeys : Set[str], nestedGroups : dict[str, Set[str]]):
        if event in graph.excludes:
            for excluded in graph.excludes[event]:
                # If excluded events are in a group
                if excluded in nestedKeys:
                    flattenValuesExclude = cls.flattenNestedGroup(graph, nestedGroups[excluded])
                # Excluded event is a single event
                else:
                    flattenValuesExclude = {excluded}
                for x in flattenValuesExclude:
                    # Remove it from included
                    graph.marking.included.discard(x)
                    
        if event in graph.responses:
            for response in graph.responses[event]:
                # If response events are in a group
                if response in nestedKeys:
                    flattenValuesResponse = cls.flattenNestedGroup(graph, nestedGroups[response])
                # Response event is a single event
                else:
                    flattenValuesResponse = {response}
                for x in flattenValuesResponse:
                    # Add it to pending
                    graph.marking.pending.add(x)

        if event in graph.includes:
            for included in graph.includes[event]:
                # If inclded events are in a group
                if included in nestedKeys:
                    print(included)
                    flattenValuesInclude = cls.flattenNestedGroup(graph, nestedGroups[included])
                # Included event is a single event
                else:
                    flattenValuesInclude = {included}
                for x in flattenValuesInclude:
                    # Add it to included
                    graph.marking.included.add(x)     

    @classmethod
    # Evaluate enabled events (evaluate possible next steps)
    def enabled(cls, graph : DcrGraph) -> Set[str]:
        res = super().enabled(graph)
        nestGroups : dict = graph.nestedgroups
        nested_keys : Set = set(nestGroups.keys())
        eventsNotExecuted : Set[str] = graph.marking.included.difference(graph.marking.executed).intersection(res)
       
        for conditions in zip(graph.conditions.keys(), graph.conditions.values()):
            key = conditions[0]
            value = conditions[1]
            
            # Group ->* something
            if cls.setElemToString(value) in nested_keys:
                # events in nested group that is a condition for something else
                conditionGroup = nestGroups[cls.setElemToString(value)]
                flattenedConditionGroup = cls.flattenNestedGroup(graph, conditionGroup)
                # events is nested group that has not been executed
                groupEventsNotExecuted = flattenedConditionGroup.intersection(eventsNotExecuted)
                
                # If there is at least one event in the group that has not been executed, remove events
                if len(groupEventsNotExecuted) > 0:
                    # If group is a condition for single event:
                    if cls.setElemToString(key) not in nested_keys:
                        res.discard(cls.setElemToString(key))
                    # If group is a condition for another group:    
                    else:
                        flattenedGroup = cls.flattenNestedGroup(graph, nestGroups[key])
                        for e in flattenedGroup:
                            res.discard(cls.setElemToString(e)) 

            # Single event ->* something
            else:
                # Check that condition event is not executed:
                if cls.setElemToString(value) in eventsNotExecuted:
                    # If single event is a condition for a group:
                    if key in nested_keys:
                        flattenedGroup = cls.flattenNestedGroup(graph, nestGroups[key])
                        for e in flattenedGroup:
                            res.discard(cls.setElemToString(e)) 
        return res
    
    @classmethod
    def execute(cls, graph, event):
        nestGroups : dict = graph.nestedgroups
        nested_values = str(graph.nestedgroups.values())
        nested_keys : Set = set(nestGroups.keys())
        
        # If event is in a group, and we want to execute the event inside a group
        # we have to get the group's relation and carry it to the event itself
        # e.g. C in N2, when it gets executed, the response relation should also fire
        if event in nested_values: 
            groups = cls.find_groups(nestGroups, event)
            # The origination of either group or event is not mutually exlusive
            # because if it was the relations from the individual event in the 
            # groups would not be exuted
            # when relation originated from group. We run the relation from the
            # Group first (in the case of the assignment 2 example) a response
            # from C and D to group with single events E and F.
            # Where after we execute C and D after the above response has been 
            # executed

            # When a relation originated from a group
            for group in groups:
                cls.execute_helper(graph, group, nested_keys, nestGroups)
            # When a relation originates from an event
            cls.execute_helper(graph, event, nested_keys, nestGroups)
            
        return super().execute(graph, event)        
