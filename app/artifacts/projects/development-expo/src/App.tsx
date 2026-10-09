import { useState } from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
export default function App() {
 const [count,setCount]=useState(0);
 return <View style={styles.page}><Text style={styles.heading}>Your workspace</Text>
 <Text>Replace this starter with the requested app.</Text>
 <Pressable accessibilityRole="button" onPress={()=>setCount(n=>n+1)} style={styles.button}>
 <Text style={{color:'white'}}>Completed {count}</Text></Pressable></View>;
}
const styles=StyleSheet.create({page:{flex:1,padding:32,backgroundColor:'#f4f7f5',justifyContent:'center'},heading:{fontSize:32,fontWeight:'700'},button:{padding:16,backgroundColor:'#0d6559',borderRadius:12,marginTop:20}});
