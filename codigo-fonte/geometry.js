export function containsLayer(layer,height,point){
 const angle=-(layer.rotation||0)*Math.PI/180,cx=layer.x+layer.w/2,cy=layer.y+height/2,dx=point.x-cx,dy=point.y-cy;
 const x=cx+dx*Math.cos(angle)-dy*Math.sin(angle),y=cy+dx*Math.sin(angle)+dy*Math.cos(angle);
 return x>=layer.x&&x<=layer.x+layer.w&&y>=layer.y&&y<=layer.y+height;
}
