import math
import random
import itertools
import collections
from tools import dropout, add_bias

try: 
    import numpypy as np
except:
    import numpy as np
   
    
default_settings = {
    # Optional settings
    "weights_low"           : -0.1,     # Lower bound on initial weight range
    "weights_high"          : 0.1,      # Upper bound on initial weight range
    
    "input_layer_dropout"   : 0.0,      # dropout fraction of the input layer
    "hidden_layer_dropout"  : 0.1,      # dropout fraction in all hidden layers
    
    "batch_size"            : 1,        # 1 := online learning, 0 := entire trainingset as batch, else := batch learning size
}

class NeuralNet:
    def __init__(self, settings ):
        self.__dict__.update( default_settings )
        self.__dict__.update( settings )
        
        assert len(self.activation_functions) == (self.n_hidden_layers + 1), \
            "Expected {n_expected} activation functions, but was initialized with {n_received}.".format(
                n_expected = (self.n_hidden_layers + 1),
                n_received = len(self.activation_functions)
            )
        
        if self.n_hidden_layers == 0:
            # Count the necessary number of weights for the input->output connection.
            # input -> [] -> output
            self.n_weights = (self.n_inputs + 1) * self.n_outputs
        else:
            # Count the necessary number of weights summed over all the layers.
            # input -> [n_hiddens -> n_hiddens] -> output
            self.n_weights = (self.n_inputs + 1) * self.n_hiddens +\
                             (self.n_hiddens**2  + self.n_hiddens) * (self.n_hidden_layers - 1) +\
                             (self.n_hiddens * self.n_outputs) + self.n_outputs
        
        # Initialize the network with new randomized weights
        self.set_weights( self.generate_weights( self.weights_low, self.weights_high ) )
    #end
    
    
    def generate_weights(self, low = -0.1, high = 0.1):
        # Generate new random weights for all the connections in the network
        if not False:
            # Support NumPy
            return [random.uniform(low,high) for _ in xrange(self.n_weights)]
        else:
            return np.random.uniform(low, high, size=(1,self.n_weights)).tolist()[0]
    #end
    
    
    def unpack(self, weight_list ):
        # This method will create a list of weight matrices. Each list element
        # corresponds to the connection between two layers.
        if self.n_hidden_layers == 0:
            return [ np.array(weight_list).reshape(self.n_inputs+1,self.n_outputs) ]
        else:
            weight_layers = [ np.array(weight_list[:(self.n_inputs+1)*self.n_hiddens]).reshape(self.n_inputs+1,self.n_hiddens) ]
            weight_layers += [ np.array(weight_list[(self.n_inputs+1)*self.n_hiddens+(i*(self.n_hiddens**2+self.n_hiddens)):(self.n_inputs+1)*self.n_hiddens+((i+1)*(self.n_hiddens**2+self.n_hiddens))]).reshape(self.n_hiddens+1,self.n_hiddens) for i in xrange(self.n_hidden_layers-1) ]
            weight_layers += [ np.array(weight_list[(self.n_inputs+1)*self.n_hiddens+((self.n_hidden_layers-1)*(self.n_hiddens**2+self.n_hiddens)):]).reshape(self.n_hiddens+1,self.n_outputs) ]
            
        return weight_layers
    #end
    
    
    def set_weights(self, weight_list ):
        # This is a helper method for setting the network weights to a previously defined list.
        # This is useful for utilizing a previously optimized neural network weight set.
        self.weights = self.unpack( weight_list )
    #end
    
    
    def get_weights(self, ):
        # This will stack all the weights in the network on a list, which may be saved to the disk.
        return [w for l in self.weights for w in l.flat]
    #end
    
    def backpropagation(self, trainingset, ERROR_LIMIT = 1e-3, learning_rate = 0.3, momentum_factor = 0.9  ):
        
        assert trainingset[0].features.shape[0] == self.n_inputs, \
                "ERROR: input size varies from the defined input setting"
        
        assert trainingset[0].targets.shape[0]  == self.n_outputs, \
                "ERROR: output size varies from the defined output setting"
        
        
        training_data    = np.array( [instance.features for instance in trainingset ] )
        training_targets = np.array( [instance.targets for instance in trainingset ] )
        
        MSE              = ( ) # inf
        neterror         = None
        momentum         = collections.defaultdict( int )
        
        batch_size       = self.batch_size if self.batch_size != 0 else training_data.shape[0]
        
        epoch = 0
        while MSE > ERROR_LIMIT:
            epoch += 1
            
            for start in xrange( 0, len(training_data), batch_size ):
                batch             = training_data[start : start+batch_size]
                input_layers      = self.update( training_data, trace=True )
                out               = input_layers[-1]
                              
                error             = out - training_targets
                delta             = error
                MSE               = np.mean( np.power(error,2) )
            
            
                loop  = itertools.izip(
                                xrange(len(self.weights)-1, -1, -1),
                                reversed(self.weights),
                                reversed(input_layers[:-1]),
                            )
            
                for i, weight_layer, input_signals in loop:
                    # Loop over the weight layers in reversed order to calculate the deltas
                
                    if i == 0:
                        dropped = dropout( add_bias(input_signals).T, self.input_layer_dropout  )
                    else:
                        dropped = dropout( add_bias(input_signals).T, self.hidden_layer_dropout )
                
                    # Calculate weight change
                    dW = learning_rate * np.dot( dropped, delta ) + momentum_factor * momentum[i]
                
                    if i!= 0:
                        """Do not calculate the delta unnecessarily."""
                        # Skipping the bias weight during calculation.
                        weight_delta = np.dot( delta, weight_layer[1:,:].T )
            
                        # Calculate the delta for the subsequent layer
                        delta = np.multiply(  weight_delta, self.activation_functions[i-1]( input_signals, derivative=True) )
                
                    # Store the momentum
                    momentum[i] = dW
                
                    # Update the weights
                    self.weights[ i ] -= dW
            
            if epoch%1000==0:
                # Show the current training status
                print "* current network error (MSE):", MSE
        
        print "* Converged to error bound (%.4g) with MSE = %.4g." % ( ERROR_LIMIT, MSE )
        print "* Trained for %d epochs." % epoch
    # end backprop
    
    
    def update(self, input_values, trace=False ):
        # This is a forward operation in the network. This is how we 
        # calculate the network output from a set of input signals.
        
        output = input_values
        if trace: tracelist = [ output ]
        
        for i, weight_layer in enumerate(self.weights):
            # Loop over the network layers and calculate the output
            if i == 0:
                output = np.dot( output, weight_layer[1:,:] ) + weight_layer[0:1,:] # implicit bias
            else:
                output = np.dot( output, weight_layer[1:,:] ) + weight_layer[0:1,:] # implicit bias
            
            output = self.activation_functions[i]( output )
            if trace: tracelist.append( output )
        
        if trace: return tracelist
        
        return output
    #end
    
    
    def save_to_file(self, filename = "network.pkl" ):
        import cPickle
        """
        This save method pickles the parameters of the current network into a 
        binary file for persistant storage.
        """
        with open( filename , 'wb') as file:
            store_dict = {
                "n_inputs"             : self.n_inputs,
                "n_outputs"            : self.n_outputs,
                "n_hiddens"            : self.n_hiddens,
                "n_hidden_layers"      : self.n_hidden_layers,
                "activation_functions" : self.activation_functions,
                "n_weights"            : self.n_weights,
                "weights"              : self.weights

            }
            cPickle.dump( store_dict, file, 2 )
    #end
    
    @staticmethod
    def load_from_file( filename = "network.pkl" ):
        """
        Load the complete configuration of a previously stored network.
        """
        network = NeuralNet( 0, 0, 0, 0, [0] )
        
        with open( filename , 'rb') as file:
            import cPickle
            store_dict = cPickle.load(file)
            
            network.n_inputs             = store_dict["n_inputs"]            
            network.n_outputs            = store_dict["n_outputs"]           
            network.n_hiddens            = store_dict["n_hiddens"]           
            network.n_hidden_layers      = store_dict["n_hidden_layers"]     
            network.n_weights            = store_dict["n_weights"]           
            network.weights              = store_dict["weights"]             
            network.activation_functions = store_dict["activation_functions"]
        
        return network
    #end
#end class